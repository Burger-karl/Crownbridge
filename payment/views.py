# payment/views.py
import json
import logging
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import transaction, models
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from users.models import CustomUser
from .forms import WithdrawalRequestForm, TransferForm, DepositForm, P2PTransferForm
from .models import (
    WithdrawalRequest, UserBalance, Transaction,
    Deposit, PlatformWallet, DepositAddress, P2PTransfer,
)
from .deposit_processor import finalize_deposit
from .constants import RECEIVER_ADDRESSES
from .services.p2ptransfer import p2p_transfer

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Withdrawal
# ------------------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def withdraw_page(request):
    from investment.models import UserInvestment
    investments = UserInvestment.objects.filter(user=request.user)
    total_invested = sum((inv.amount_invested for inv in investments), Decimal("0"))
    total_expected_profit = sum((inv.calculate_expected_profit() for inv in investments), Decimal("0"))
    ub, _ = UserBalance.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = WithdrawalRequestForm(request.POST, user=request.user)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            chain = form.cleaned_data["chain"]
            to_address_raw = form.cleaned_data["to_address"].split(":", 1)[-1]

            if amount <= Decimal("0"):
                messages.error(request, "Enter a valid withdrawal amount.")
                return redirect("payment:withdraw")

            if ub.balance < amount:
                messages.error(request, "Insufficient balance for this withdrawal.")
                return redirect("payment:withdraw")

            # Debit the balance immediately when the request is submitted
            # so users cannot double-spend a pending withdrawal
            with transaction.atomic():
                ub_locked = UserBalance.objects.select_for_update().get(user=request.user)
                if ub_locked.balance < amount:
                    messages.error(request, "Insufficient balance.")
                    return redirect("payment:withdraw")

                wr = WithdrawalRequest.objects.create(
                    user=request.user,
                    amount=amount,
                    chain=chain,
                    to_address=to_address_raw,
                    status="pending",
                )
                ub_locked.debit(
                    amount,
                    note=f"Withdrawal request #{wr.id}",
                    reference=str(wr.id),
                )

            messages.success(request, "Withdrawal request submitted. Processing will begin shortly.")
            return redirect("payment:withdrawals")
    else:
        form = WithdrawalRequestForm(initial={"chain": "ethereum"}, user=request.user)

    return render(request, "payment/withdrawal_request.html", {
        "form": form,
        "total_invested": total_invested,
        "total_expected_profit": total_expected_profit,
        "user_balance": ub.balance,
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
@require_POST
def approve_withdrawal(request, wid):
    withdrawal = get_object_or_404(WithdrawalRequest, id=wid, status="pending")
    withdrawal.status = "approved"
    withdrawal.processed_at = timezone.now()
    withdrawal.admin_note = (withdrawal.admin_note or "") + f"\nApproved by {request.user}"
    withdrawal.save(update_fields=["status", "processed_at", "admin_note"])
    messages.success(request, "Withdrawal approved. Proceed to payment.")
    return redirect("payment:admin_pending_withdrawals")


@staff_member_required
@require_POST
def decline_withdrawal(request, wid):
    wr = get_object_or_404(WithdrawalRequest, pk=wid)
    if wr.status != "pending":
        messages.error(request, "Withdrawal is not in pending status.")
        return redirect("payment:admin_pending_withdrawals")

    with transaction.atomic():
        wr.status = "rejected"
        wr.processed_at = timezone.now()
        wr.admin_note = (wr.admin_note or "") + f"\nRejected by {request.user} at {wr.processed_at}"
        wr.save(update_fields=["status", "processed_at", "admin_note"])

        # Refund the user's balance since it was debited on submission
        ub, _ = UserBalance.objects.get_or_create(user=wr.user)
        ub.credit(
            wr.amount,
            note=f"Refund for rejected withdrawal #{wr.id}",
            reference=f"refund_{wr.id}",
        )

    messages.info(request, f"Withdrawal {wr.id} rejected and amount refunded to user.")
    return redirect("payment:admin_pending_withdrawals")


@staff_member_required
def admin_withdrawal_payment(request, wid):
    from payment.services.btc_withdrawal import send_btc_tatum
    from payment.services.eth_withdrawal import send_eth, send_usdt_erc20
    from payment.services.tron_withdrawal import send_trx, send_usdt_trc20

    withdrawal = get_object_or_404(WithdrawalRequest, id=wid, status="approved")

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid amount.")
            return redirect("payment:admin_pending_withdrawals")

        chain = request.POST.get("chain")

        try:
            withdrawal.status = "processing"
            withdrawal.save(update_fields=["status"])

            chain_map = {
                "bitcoin": lambda: send_btc_tatum(withdrawal.to_address, amount),
                "ethereum": lambda: send_eth(withdrawal.to_address, amount),
                "tron": lambda: send_trx(withdrawal.to_address, amount),
                "usdt_erc20": lambda: send_usdt_erc20(withdrawal.to_address, amount),
                "usdt_trc20": lambda: send_usdt_trc20(withdrawal.to_address, amount),
            }

            if chain not in chain_map:
                raise ValueError(f"Unsupported chain: {chain}")

            tx_hash = chain_map[chain]()

            withdrawal.tx_hash = tx_hash
            withdrawal.status = "sent"
            withdrawal.processed_at = timezone.now()
            withdrawal.save()

            logger.info("Withdrawal %s sent on chain %s, tx=%s", wid, chain, tx_hash)
            messages.success(request, f"Withdrawal sent. TX: {tx_hash}")
            return redirect("payment:admin_pending_withdrawals")

        except Exception as e:
            withdrawal.status = "failed"
            withdrawal.admin_note = (withdrawal.admin_note or "") + f"\nFailed: {e}"
            withdrawal.save(update_fields=["status", "admin_note"])
            logger.error("Withdrawal %s failed: %s", wid, e)
            messages.error(request, f"Payment failed: {e}")

    return render(request, "payment/withdrawal_payment.html", {
        "withdrawal": withdrawal,
        "receiver_addresses": RECEIVER_ADDRESSES,
    })


# ------------------------------------------------------------------
# Deposits
# ------------------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def deposit_page(request):
    profile = request.user.profile

    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
            chain = form.cleaned_data["chain"]
            amount = form.cleaned_data["amount"]
            platform_wallet = get_object_or_404(PlatformWallet, chain=chain)

            deposit = Deposit.objects.create(
                user=request.user,
                platform_wallet=platform_wallet,
                amount=amount,
                tx_hash=f"intent_{uuid4().hex}",
                status="pending",
                credited=False,
            )
            messages.success(request, "Deposit intent created.")
            return redirect("payment:deposit_instructions", deposit_id=deposit.id)
    else:
        form = DepositForm()

    wallet_addresses = {
        "Bitcoin (BTC)": profile.bitcoin_id,
        "Ethereum (ETH)": profile.ethereum_id,
        "USDT (TRC20)": profile.usdt_trc20_id,
        "Tron (TRX)": profile.tron_id,
        "BEP20": profile.bep20_id,
    }

    return render(request, "payment/deposit_page.html", {
        "form": form,
        "wallet_addresses": wallet_addresses,
    })


@login_required
def deposit_instructions(request, deposit_id):
    deposit = get_object_or_404(Deposit, id=deposit_id, user=request.user)
    receiver_address = deposit.platform_wallet.address if deposit.platform_wallet else None

    return render(request, "payment/deposit_instructions.html", {
        "deposit": deposit,
        "receiver_address": receiver_address,
        "chain": deposit.platform_wallet.chain if deposit.platform_wallet else None,
    })


@login_required
def deposit_history(request):
    deposits = Deposit.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "payment/deposit_history.html", {"deposits": deposits})


@login_required
@require_POST
def confirm_tron_deposit(request):
    from .services.tron import verify_tron_transaction

    tx_hash = request.POST.get("tx_hash", "").strip()
    if not tx_hash:
        messages.error(request, "Transaction hash is required.")
        return redirect("payment:deposit_history")

    deposit = get_object_or_404(Deposit, tx_hash=tx_hash, user=request.user, status="pending")

    result = verify_tron_transaction(
        tx_hash=tx_hash,
        expected_to=deposit.platform_wallet.address,
        expected_amount=deposit.amount,
    )

    if not result:
        messages.error(request, "Transaction not confirmed on-chain yet. Please try again later.")
        return redirect("payment:deposit_history")

    with transaction.atomic():
        deposit.status = "confirmed"
        deposit.from_address = result["from"]
        deposit.confirmations = result["confirmations"]
        deposit.save(update_fields=["status", "from_address", "confirmations"])

    messages.success(request, "Deposit confirmed and balance credited.")
    return redirect("payment:deposit_history")


@login_required
@require_POST
def confirm_eth_deposit(request):
    from .services.ethereum import verify_eth_transfer, verify_erc20_usdt

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    tx_hash = data.get("tx_hash", "").strip()
    if not tx_hash:
        return JsonResponse({"error": "tx_hash is required"}, status=400)

    deposit = (
        Deposit.objects
        .filter(user=request.user, status="pending")
        .order_by("-created_at")
        .first()
    )

    if not deposit:
        return JsonResponse({"error": "No pending deposit found"}, status=400)

    chain = deposit.platform_wallet.chain if deposit.platform_wallet else ""

    if chain == "ethereum":
        result = verify_eth_transfer(tx_hash, deposit.platform_wallet.address, deposit.amount)
    elif chain in ("usdt_erc20", "bsc"):
        result = verify_erc20_usdt(tx_hash, deposit.platform_wallet.address, deposit.amount)
    else:
        return JsonResponse({"error": f"Unsupported chain: {chain}"}, status=400)

    if not result:
        return JsonResponse({"error": "Transaction not confirmed on-chain"}, status=400)

    with transaction.atomic():
        deposit.tx_hash = tx_hash
        deposit.from_address = result["from"]
        deposit.confirmations = result.get("confirmations", 0)
        deposit.status = "confirmed"
        deposit.save()

    return JsonResponse({"success": True})


@login_required
@require_POST
def confirm_btc_deposit(request):
    from .services.bitcoin import verify_btc_transaction

    tx_hash = request.POST.get("tx_hash", "").strip()
    if not tx_hash:
        messages.error(request, "Transaction hash is required.")
        return redirect("payment:deposit_history")

    deposit = get_object_or_404(Deposit, user=request.user, status="pending")

    result = verify_btc_transaction(tx_hash, deposit.platform_wallet.address, deposit.amount)

    if not result or result["confirmations"] < 2:
        messages.error(request, "Transaction not yet confirmed (needs at least 2 confirmations).")
        return redirect("payment:deposit_history")

    deposit.tx_hash = tx_hash
    deposit.confirmations = result["confirmations"]
    deposit.status = "confirmed"
    deposit.save()

    finalize_deposit(deposit)

    messages.success(request, "Bitcoin deposit confirmed.")
    return redirect("payment:deposit_history")


# ------------------------------------------------------------------
# Transfers
# ------------------------------------------------------------------

@login_required
def transfer_history(request):
    txs = Transaction.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "payment/transfer_history.html", {"transactions": txs})


@login_required
@require_http_methods(["GET", "POST"])
def p2p_transfer_view(request):
    if request.method == "POST":
        form = P2PTransferForm(request.POST)
        if form.is_valid():
            receiver_email = form.cleaned_data["receiver_email"]
            amount = form.cleaned_data["amount"]
            chain = form.cleaned_data["chain"]

            if receiver_email == request.user.email:
                messages.error(request, "You cannot transfer to yourself.")
                return redirect("payment:p2ptransfer")

            try:
                receiver = CustomUser.objects.get(email=receiver_email)
            except CustomUser.DoesNotExist:
                messages.error(request, "No user found with that email address.")
                return redirect("payment:p2ptransfer")

            try:
                p2p_transfer(sender=request.user, receiver=receiver, amount=amount, chain=chain)
                messages.success(request, f"Sent {amount} {chain.upper()} to {receiver.email}.")
                return redirect("payment:transfer_history")
            except Exception as e:
                logger.error("P2P transfer error: %s", e)
                messages.error(request, str(e))
                return redirect("payment:p2ptransfer")
    else:
        form = P2PTransferForm()

    return render(request, "payment/p2p_transfer.html", {"form": form})


@login_required
def transaction_history_view(request):
    user = request.user

    deposits = Deposit.objects.filter(user=user).annotate(
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

    all_txs = list(deposits) + list(withdrawals) + list(sent_transfers) + list(received_transfers)
    all_txs.sort(
        key=lambda x: getattr(x, "created_at", None) or getattr(x, "requested_at", None),
        reverse=True,
    )

    paginator = Paginator(all_txs, 10)
    tx_page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "payment/transaction_history.html", {"tx_page_obj": tx_page_obj})