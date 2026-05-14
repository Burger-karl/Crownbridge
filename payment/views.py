# payment/views.py
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
import json
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from uuid import uuid4
from users.models import CustomUser
from .forms import WithdrawalRequestForm, TransferForm, DepositForm
from .models import WithdrawalRequest, UserBalance, Transaction, Deposit, PlatformWallet, DepositAddress
from .deposit_processor import finalize_deposit
from .constants import RECEIVER_ADDRESSES
from payment.services.btc_withdrawal import send_btc_tatum


def is_staff(user):
    return user.is_staff


# ── Wallet address helper ─────────────────────────────────────────────────────

def get_user_wallet_addresses(profile):
    """
    Returns a dict of { label: address } for wallets the user has saved.
    Only non-empty values are included.
    """
    mapping = [
        ("Bitcoin (BTC)",  profile.bitcoin_id),
        ("Ethereum (ETH)", profile.ethereum_id),
        ("USDT (TRC20)",   profile.usdt_trc20_id),
        ("Tron (TRX)",     profile.tron_id),
        ("BEP20",          profile.bep20_id),
    ]
    return {label: addr for label, addr in mapping if addr}


def get_receiver_address_for_chain(chain):
    """
    Returns the platform receiver address for a given chain key.
    Falls back to PlatformWallet.address if set, otherwise RECEIVER_ADDRESSES constant.
    """
    # prefer PlatformWallet address if one is configured in DB
    try:
        pw = PlatformWallet.objects.get(chain=chain)
        if pw.address:
            return pw.address
    except PlatformWallet.DoesNotExist:
        pass
    # fall back to constants.py
    return RECEIVER_ADDRESSES.get(chain, "")


# ── Withdraw ──────────────────────────────────────────────────────────────────

@login_required
def withdraw_page(request):
    from investment.models import UserInvestment
    investments = UserInvestment.objects.filter(user=request.user)

    total_invested         = sum((inv.amount_invested for inv in investments), Decimal("0"))
    total_expected_profit  = sum((inv.calculate_expected_profit() for inv in investments), Decimal("0"))

    ub, _ = UserBalance.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = WithdrawalRequestForm(request.POST, user=request.user)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            chain  = form.cleaned_data["chain"]
            to_address_raw = form.cleaned_data["to_address"].split(":", 1)[1]

            if amount <= Decimal("0"):
                messages.error(request, "Enter a valid amount.")
                return redirect("payment:withdraw")

            if ub.balance < amount:
                messages.error(request, "Insufficient balance for withdrawal.")
                return redirect("payment:withdraw")

            WithdrawalRequest.objects.create(
                user=request.user,
                amount=amount,
                chain=chain,
                to_address=to_address_raw,
                status="pending"
            )
            messages.success(request, "Withdrawal submitted — processing.")
            return redirect("payment:withdrawals")
    else:
        form = WithdrawalRequestForm(initial={"chain": "ethereum"}, user=request.user)

    return render(request, "payment/withdrawal_request.html", {
        "form":                  form,
        "total_invested":        total_invested,
        "total_expected_profit": total_expected_profit,
        "user_balance":          ub.balance,
    })


@login_required
def withdrawal_history(request):
    withdrawals = WithdrawalRequest.objects.filter(user=request.user).order_by("-requested_at")
    return render(request, "payment/withdrawal_history.html", {"withdrawals": withdrawals})


@staff_member_required
def pending_withdrawals(request):
    pending = WithdrawalRequest.objects.filter(status="pending").order_by("requested_at")
    return render(request, "payment/admin_pending_withdrawals.html", {"pending": pending})


@staff_member_required
def decline_withdrawal(request, wid):
    wr = get_object_or_404(WithdrawalRequest, pk=wid)
    if wr.status != "pending":
        messages.error(request, "Withdrawal is not pending.")
        return redirect("payment:admin_pending_withdrawals")

    wr.status       = "rejected"
    wr.processed_at = timezone.now()
    wr.admin_note   = (wr.admin_note or "") + f"\nRejected by {request.user} at {wr.processed_at}"
    wr.save(update_fields=["status", "processed_at", "admin_note"])

    messages.info(request, f"Rejected withdrawal {wr.id}.")
    return redirect("payment:admin_pending_withdrawals")


@staff_member_required
def admin_withdrawal_payment(request, wid):
    from payment.services.eth_withdrawal import send_eth, send_usdt_erc20
    from payment.services.tron_withdrawal import send_trx, send_usdt_trc20

    withdrawal = get_object_or_404(WithdrawalRequest, id=wid, status="approved")

    if request.method == "POST":
        amount = Decimal(request.POST.get("amount"))
        chain  = request.POST.get("chain")

        try:
            withdrawal.status = "processing"
            withdrawal.save(update_fields=["status"])

            if chain == "bitcoin":
                tx_hash = send_btc_tatum(withdrawal.to_address, amount)
            elif chain == "ethereum":
                tx_hash = send_eth(withdrawal.to_address, amount)
            elif chain == "tron":
                tx_hash = send_trx(withdrawal.to_address, amount)
            elif chain == "usdt_erc20":
                tx_hash = send_usdt_erc20(withdrawal.to_address, amount)
            elif chain == "usdt_trc20":
                tx_hash = send_usdt_trc20(withdrawal.to_address, amount)
            else:
                raise Exception("Unsupported chain")

            withdrawal.tx_hash      = tx_hash
            withdrawal.status       = "sent"
            withdrawal.processed_at = timezone.now()
            withdrawal.save()

            messages.success(request, "Withdrawal sent successfully.")
            return redirect("payment:admin_pending_withdrawals")

        except Exception as e:
            withdrawal.status     = "failed"
            withdrawal.admin_note = str(e)
            withdrawal.save()
            messages.error(request, f"Payment failed: {e}")

    return render(request, "payment/withdrawal_payment.html", {
        "withdrawal":        withdrawal,
        "receiver_addresses": RECEIVER_ADDRESSES,
    })


@staff_member_required
def approve_withdrawal(request, wid):
    withdrawal = get_object_or_404(WithdrawalRequest, id=wid, status="pending")
    withdrawal.status       = "approved"
    withdrawal.processed_at = timezone.now()
    withdrawal.admin_note   = (withdrawal.admin_note or "") + f"\nApproved by {request.user}"
    withdrawal.save(update_fields=["status", "processed_at", "admin_note"])
    messages.success(request, "Withdrawal approved. Proceed to payment.")
    return redirect("payment:admin_pending_withdrawals")


# ── Deposit page ──────────────────────────────────────────────────────────────

@login_required
def deposit_page(request):
    profile = request.user.profile

    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
            chain  = form.cleaned_data["chain"]
            amount = form.cleaned_data["amount"]

            platform_wallet = get_object_or_404(PlatformWallet, chain=chain)

            deposit = Deposit.objects.create(
                user=request.user,
                platform_wallet=platform_wallet,
                amount=amount,
                tx_hash=f"intent_{uuid4().hex}",
                status="pending",
                credited=False,
                admin_approved=False,       # ← requires admin approval
            )

            messages.success(request, "Deposit intent created.")
            return redirect("payment:deposit_instructions", deposit_id=deposit.id)
    else:
        form = DepositForm()

    # Build wallet addresses from profile for the dropdown
    wallet_addresses = get_user_wallet_addresses(profile)

    return render(request, "payment/deposit_page.html", {
        "form":             form,
        "wallet_addresses": wallet_addresses,
    })


# ── Deposit instructions ──────────────────────────────────────────────────────

@login_required
def deposit_instructions(request, deposit_id):
    deposit = get_object_or_404(Deposit, id=deposit_id, user=request.user)

    chain = deposit.platform_wallet.chain if deposit.platform_wallet else None

    # Get the correct receiver address for this chain
    receiver_address = get_receiver_address_for_chain(chain) if chain else ""

    return render(request, "payment/deposit_instructions.html", {
        "deposit":          deposit,
        "receiver_address": receiver_address,
        "chain":            chain,
    })


# ── Deposit history ───────────────────────────────────────────────────────────

@login_required
def deposit_history(request):
    """
    Show only deposits that have been admin-approved OR are still pending.
    Rejected deposits are hidden from user view.
    """
    deposits = Deposit.objects.filter(
        user=request.user
    ).exclude(
        status="rejected"
    ).order_by("-created_at")
    return render(request, "payment/deposit_history.html", {"deposits": deposits})


# ── Admin deposit approval view ───────────────────────────────────────────────

@staff_member_required
def admin_pending_deposits(request):
    """
    Staff view: lists all deposits awaiting admin approval.
    Shows confirmed deposits that have not yet been approved.
    """
    pending = Deposit.objects.filter(
        admin_approved=False
    ).exclude(
        status="rejected"
    ).order_by("created_at").select_related("user", "platform_wallet")

    return render(request, "payment/admin_pending_deposits.html", {"pending": pending})


from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from .models import Deposit, UserBalance


@staff_member_required
@transaction.atomic
def admin_approve_deposit(request, deposit_id):
    """
    Production-safe deposit approval.

    - Prevents double-crediting
    - Uses row locking
    - Credits balance immediately
    - Marks deposit as credited
    """

    deposit = (
        Deposit.objects
        .select_for_update()
        .select_related("user")
        .get(id=deposit_id)
    )

    if deposit.admin_approved:
        messages.info(request, "Deposit already approved.")
        return redirect("payment:admin_pending_deposits")

    if deposit.status not in ("confirmed", "pending"):
        messages.error(
            request,
            f"Cannot approve deposit with status '{deposit.status}'."
        )
        return redirect("payment:admin_pending_deposits")

    # If admin verified payment manually
    if deposit.status == "pending":
        deposit.status = "confirmed"

    # Lock user balance row
    user_balance, _ = (
        UserBalance.objects
        .select_for_update()
        .get_or_create(user=deposit.user)
    )

    # Prevent duplicate crediting
    if deposit.credited:
        messages.warning(request, "Deposit already credited.")
        return redirect("payment:admin_pending_deposits")

    # CREDIT USER
    user_balance.balance += deposit.amount
    user_balance.save(update_fields=["balance"])

    # MARK DEPOSIT
    deposit.admin_approved = True
    deposit.admin_approved_by = request.user
    deposit.admin_approved_at = timezone.now()
    deposit.credited = True

    deposit.save(update_fields=[
        "status",
        "admin_approved",
        "admin_approved_by",
        "admin_approved_at",
        "credited",
    ])

    messages.success(
        request,
        f"${deposit.amount} credited successfully to {deposit.user.email}"
    )

    return redirect("payment:admin_pending_deposits")

@staff_member_required
def admin_reject_deposit(request, deposit_id):
    """Reject a deposit — user balance is NOT credited."""
    deposit = get_object_or_404(Deposit, id=deposit_id)

    if deposit.credited:
        messages.error(request, "Cannot reject a deposit that has already been credited.")
        return redirect("payment:admin_pending_deposits")

    deposit.status     = "rejected"
    deposit.admin_note = (deposit.admin_note or "") + f"\nRejected by {request.user} at {timezone.now()}"
    deposit.save(update_fields=["status", "admin_note"])

    messages.info(request, f"Deposit {deposit.id} rejected.")
    return redirect("payment:admin_pending_deposits")


# ── Tron confirm ──────────────────────────────────────────────────────────────

from django.views.decorators.http import require_POST
from payment.services.tron import verify_tron_transaction


@login_required
@require_POST
def confirm_tron_deposit(request):
    tx_hash = request.POST.get("tx_hash")
    deposit = get_object_or_404(Deposit, tx_hash=tx_hash, user=request.user, status="pending")

    result = verify_tron_transaction(
        tx_hash=tx_hash,
        expected_to=deposit.platform_wallet.address,
        expected_amount=deposit.amount,
    )

    if not result:
        messages.error(request, "Transaction not confirmed on blockchain yet.")
        return redirect("payment:deposit_history")

    with transaction.atomic():
        deposit.status       = "confirmed"
        deposit.from_address = result["from"]
        deposit.confirmations = result["confirmations"]
        deposit.save(update_fields=["status", "from_address", "confirmations"])
        # balance NOT credited yet — admin must approve first

    messages.success(request, "Deposit confirmed on blockchain. Awaiting admin approval before balance is credited.")
    return redirect("payment:deposit_history")


# ── ETH confirm ───────────────────────────────────────────────────────────────

from payment.services.ethereum import verify_eth_transfer, verify_erc20_usdt


@login_required
@require_POST
def confirm_eth_deposit(request):
    data    = json.loads(request.body)
    tx_hash = data.get("tx_hash")

    deposit = Deposit.objects.filter(
        user=request.user,
        status="pending"
    ).last()

    if not deposit:
        return JsonResponse({"error": "No pending deposit found"}, status=400)

    if deposit.platform_wallet and deposit.platform_wallet.chain == "ethereum":
        result = verify_eth_transfer(
            tx_hash,
            expected_to=deposit.platform_wallet.address,
            expected_amount=deposit.amount,
        )
    else:
        result = verify_erc20_usdt(
            tx_hash,
            expected_to=deposit.platform_wallet.address,
            expected_amount=deposit.amount,
        )

    if not result:
        return JsonResponse({"error": "Transaction not confirmed"}, status=400)

    with transaction.atomic():
        deposit.tx_hash       = tx_hash
        deposit.from_address  = result["from"]
        deposit.confirmations = result.get("confirmations", 0)
        deposit.status        = "confirmed"
        deposit.save()
        # balance NOT credited yet — admin must approve first

    return JsonResponse({"success": True, "message": "Deposit confirmed. Awaiting admin approval."})


# ── BTC confirm ───────────────────────────────────────────────────────────────

from payment.services.bitcoin import verify_btc_transaction


@login_required
def confirm_btc_deposit(request):
    tx_hash = request.POST.get("tx_hash")
    deposit = get_object_or_404(Deposit, user=request.user, status="pending")

    result = verify_btc_transaction(
        tx_hash,
        expected_to=deposit.platform_wallet.address,
        expected_amount=deposit.amount,
    )

    if not result or result["confirmations"] < 2:
        messages.error(request, "Transaction not confirmed yet.")
        return redirect("payment:deposit_history")

    deposit.tx_hash       = tx_hash
    deposit.confirmations = result["confirmations"]
    deposit.status        = "confirmed"
    deposit.save()
    # balance NOT credited yet — admin must approve first

    messages.success(request, "Bitcoin deposit confirmed. Awaiting admin approval before balance is credited.")
    return redirect("payment:deposit_history")


# ── Transfers ─────────────────────────────────────────────────────────────────

@login_required
def transfer_history(request):
    txs = Transaction.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "payment/transfer_history.html", {"transactions": txs})


from .models import P2PTransfer
from .forms import P2PTransferForm
from .services.p2ptransfer import p2p_transfer


@login_required
def p2p_transfer_view(request):
    if request.method == "POST":
        form = P2PTransferForm(request.POST)
        if form.is_valid():
            receiver_email = form.cleaned_data["receiver_email"]
            amount         = form.cleaned_data["amount"]
            chain          = form.cleaned_data["chain"]

            try:
                receiver = CustomUser.objects.get(email=receiver_email)
                p2p_transfer(sender=request.user, receiver=receiver, amount=amount, chain=chain)
                messages.success(request, f"Sent {amount} {chain.upper()} to {receiver.email}")
                return redirect("payment:transfer_history")
            except Exception as e:
                messages.error(request, str(e))
                return redirect("payment:p2ptransfer")
    else:
        form = P2PTransferForm()

    return render(request, "payment/p2p_transfer.html", {"form": form})


# ── Transaction history ───────────────────────────────────────────────────────

from django.db.models import Q
from django.core.paginator import Paginator


@login_required
def transaction_history_view(request):
    user = request.user

    deposits = Deposit.objects.filter(user=user).exclude(status="rejected").annotate(
        tx_type=models.Value("Deposit", output_field=models.CharField())
    )
    withdrawals = WithdrawalRequest.objects.filter(user=user).annotate(
        tx_type=models.Value("Withdrawal", output_field=models.CharField())
    )
    sent_transfers = P2PTransfer.objects.filter(sender=user).annotate(
        tx_type=models.Value("P2P Sent", output_field=models.CharField())
    )
    received_transfers = P2PTransfer.objects.filter(receiver=user).annotate(
        tx_type=models.Value("P2P Received", output_field=models.CharField())
    )

    transactions = (
        list(deposits) + list(withdrawals) +
        list(sent_transfers) + list(received_transfers)
    )
    transactions.sort(
        key=lambda x: getattr(x, "created_at", None) or getattr(x, "processed_at", None),
        reverse=True
    )

    paginator    = Paginator(transactions, 10)
    tx_page_obj  = paginator.get_page(request.GET.get("page"))

    return render(request, "payment/transaction_history.html", {"tx_page_obj": tx_page_obj})


from django.db import models