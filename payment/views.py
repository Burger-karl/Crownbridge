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
from payment.services.btc_withdrawal import send_btc_tatum

# helper
def is_staff(user):
    return user.is_staff

@login_required
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

            # extract raw wallet value after prefix removal
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
        "form": form,
        "total_invested": total_invested,
        "total_expected_profit": total_expected_profit,
        "user_balance": ub.balance,
    })


@login_required
def withdrawal_history(request):
    """
    List user's withdrawals and show action buttons depending on status:
    - pending: show disabled 'Processing' button
    - approved: show button linking to payment page
    - rejected: show 'Declined' button linking to dashboard
    """
    withdrawals = WithdrawalRequest.objects.filter(user=request.user).order_by("-requested_at")
    return render(request, "payment/withdrawal_history.html", {"withdrawals": withdrawals})


@staff_member_required
def pending_withdrawals(request):
    """
    Staff view listing pending withdrawal requests with Approve/Decline actions.
    """
    pending = WithdrawalRequest.objects.filter(status="pending").order_by("requested_at")
    return render(request, "payment/admin_pending_withdrawals.html", {"pending": pending})


@staff_member_required
def decline_withdrawal(request, wid):
    """
    Decline a pending withdrawal: mark as 'rejected' and optionally notify user.
    """
    wr = get_object_or_404(WithdrawalRequest, pk=wid)
    if wr.status != "pending":
        messages.error(request, "Withdrawal is not pending.")
        return redirect("payment:admin_pending_withdrawals")

    wr.status = "rejected"
    wr.processed_at = timezone.now()
    wr.admin_note = (wr.admin_note or "") + f"\nRejected by {request.user} at {wr.processed_at}"
    wr.save(update_fields=["status", "processed_at", "admin_note"])

    messages.info(request, f"Rejected withdrawal {wr.id}.")
    return redirect("payment:admin_pending_withdrawals")


from payment.constants import RECEIVER_ADDRESSES
from decimal import Decimal

@staff_member_required
def admin_withdrawal_payment(request, wid):
    withdrawal = get_object_or_404(
        WithdrawalRequest,
        id=wid,
        status="approved"
    )

    if request.method == "POST":
        amount = Decimal(request.POST.get("amount"))
        chain = request.POST.get("chain")

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

            withdrawal.tx_hash = tx_hash
            withdrawal.status = "sent"
            withdrawal.processed_at = timezone.now()
            withdrawal.save()

            messages.success(request, "Withdrawal sent successfully.")
            return redirect("payment:admin_pending_withdrawals")

        except Exception as e:
            withdrawal.status = "failed"
            withdrawal.admin_note = str(e)
            withdrawal.save()
            messages.error(request, f"Payment failed: {e}")

    return render(request, "payment/withdrawal_payment.html", {
        "withdrawal": withdrawal,
        "receiver_addresses": RECEIVER_ADDRESSES
    })

from payment.services.eth_withdrawal import send_eth, send_usdt_erc20
from payment.services.tron_withdrawal import send_trx, send_usdt_trc20


@staff_member_required
def approve_withdrawal(request, wid):
    withdrawal = get_object_or_404(
        WithdrawalRequest,
        id=wid,
        status="pending"
    )

    withdrawal.status = "approved"
    withdrawal.processed_at = timezone.now()
    withdrawal.admin_note = (withdrawal.admin_note or "") + f"\nApproved by {request.user}"
    withdrawal.save(update_fields=["status", "processed_at", "admin_note"])

    messages.success(request, "Withdrawal approved. Proceed to payment.")
    return redirect("payment:admin_pending_withdrawals")





# -------------------------
# Deposit flows (Intent)
# -------------------------
from .constants import RECEIVER_ADDRESSES
from django.shortcuts import get_object_or_404
from uuid import uuid4

@login_required
def deposit_page(request):
    profile = request.user.profile

    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
            chain = form.cleaned_data["chain"]
            amount = form.cleaned_data["amount"]

            # ✅ SAFELY fetch PlatformWallet
            platform_wallet = get_object_or_404(PlatformWallet, chain=chain)

            deposit = Deposit.objects.create(
                user=request.user,
                platform_wallet=platform_wallet,
                amount=amount,
                tx_hash=f"intent_{uuid4().hex}",
                status="pending",
                credited=False,
            )

            messages.success(request, "Deposit intent created")
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

    return render(
        request,
        "payment/deposit_page.html",
        {
            "form": form,
            "wallet_addresses": wallet_addresses,
        },
    )

@login_required
def deposit_instructions(request, deposit_id):
    deposit = get_object_or_404(Deposit, id=deposit_id, user=request.user)

    receiver_address = None
    if deposit.platform_wallet:
        receiver_address = deposit.platform_wallet.address

    context = {
        "deposit": deposit,
        "receiver_address": receiver_address,
        "chain": deposit.platform_wallet.chain if deposit.platform_wallet else None,
    }
    return render(request, "payment/deposit_instructions.html", context)


@login_required
def deposit_history(request):
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'payment/deposit_history.html', {'deposits': deposits})


from django.views.decorators.http import require_POST
from django.db import transaction
from payment.services.tron import verify_tron_transaction


@login_required
@require_POST
def confirm_tron_deposit(request):
    tx_hash = request.POST.get("tx_hash")

    deposit = get_object_or_404(
        Deposit,
        tx_hash=tx_hash,
        user=request.user,
        status="pending"
    )

    result = verify_tron_transaction(
        tx_hash=tx_hash,
        expected_to=deposit.platform_wallet.address,
        expected_amount=deposit.amount,
    )

    if not result:
        messages.error(request, "Transaction not confirmed on blockchain yet.")
        return redirect("payment:deposit_history")

    with transaction.atomic():
        deposit.status = "confirmed"
        deposit.from_address = result["from"]
        deposit.confirmations = result["confirmations"]
        deposit.save(update_fields=["status", "from_address", "confirmations"])

        # 👇 Your signal will now credit the user
        # post_save → credit_on_confirm

    messages.success(request, "Deposit confirmed and balance credited.")
    return redirect("payment:deposit_history")


import json
from django.views.decorators.http import require_POST
from django.db import transaction
from django.http import JsonResponse
from payment.services.ethereum import (
    verify_eth_transfer,
    verify_erc20_usdt,
)


@login_required
@require_POST
def confirm_eth_deposit(request):
    data = json.loads(request.body)
    tx_hash = data.get("tx_hash")

    deposit = Deposit.objects.filter(
        user=request.user,
        chain__in=["ethereum", "usdt_erc20"],
        status="pending"
    ).last()

    if not deposit:
        return JsonResponse({"error": "No pending deposit found"}, status=400)

    if deposit.chain == "ethereum":
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
        deposit.tx_hash = tx_hash
        deposit.from_address = result["from"]
        deposit.confirmations = result.get("confirmations", 0)
        deposit.status = "confirmed"
        deposit.save()

        # balance credited via signal

    return JsonResponse({"success": True})


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from payment.services.bitcoin import verify_btc_transaction


@login_required
def confirm_btc_deposit(request):
    tx_hash = request.POST.get("tx_hash")

    deposit = get_object_or_404(
        Deposit,
        user=request.user,
        chain="bitcoin",
        status="pending"
    )

    result = verify_btc_transaction(
        tx_hash,
        expected_to=deposit.platform_wallet.address,
        expected_amount=deposit.amount,
    )

    if not result or result["confirmations"] < 2:
        messages.error(request, "Transaction not confirmed yet.")
        return redirect("payment:deposit_history")

    deposit.tx_hash = tx_hash
    deposit.confirmations = result["confirmations"]
    deposit.status = "confirmed"
    deposit.save()

    finalize_deposit(deposit)

    messages.success(request, "Bitcoin deposit confirmed.")
    return redirect("payment:deposit_history")



# -------------------------
# Transfers (internal)
# -------------------------


@login_required
def transfer_history(request):
    txs = Transaction.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'payment/transfer_history.html', {'transactions': txs})



from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from .models import P2PTransfer, Deposit
from .forms import P2PTransferForm
from users.models import CustomUser
from django.db import models

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from payment.forms import P2PTransferForm
from payment.services.p2ptransfer import p2p_transfer
from users.models import CustomUser


@login_required
def p2p_transfer_view(request):
    if request.method == "POST":
        form = P2PTransferForm(request.POST)
        if form.is_valid():
            receiver_email = form.cleaned_data["receiver_email"]
            amount = form.cleaned_data["amount"]
            chain = form.cleaned_data["chain"]

            try:
                receiver = CustomUser.objects.get(email=receiver_email)
                tx = p2p_transfer(
                    sender=request.user,
                    receiver=receiver,
                    amount=amount,
                    chain=chain
                )

                messages.success(
                    request,
                    f"Sent {amount} {chain.upper()} to {receiver.email}"
                )
                return redirect("payment:transfer_history")

            except Exception as e:
                messages.error(request, str(e))
                return redirect("payment:p2ptransfer")

    else:
        form = P2PTransferForm()

    return render(request, "payment/p2p_transfer.html", {"form": form})


# views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from payment.models import Deposit, WithdrawalRequest, P2PTransfer
from django.core.paginator import Paginator

@login_required
def transaction_history_view(request):
    user = request.user

    # Combine deposits, withdrawals, P2P transfers into one list
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

    # Merge them into a single queryset-like list
    transactions = list(deposits) + list(withdrawals) + list(sent_transfers) + list(received_transfers)

    # Sort by date
    transactions.sort(key=lambda x: getattr(x, "created_at", None) or getattr(x, "processed_at", None), reverse=True)

    # Pagination
    paginator = Paginator(transactions, 10)
    page_number = request.GET.get("page")
    tx_page_obj = paginator.get_page(page_number)

    return render(request, "payment/transaction_history.html", {
        "tx_page_obj": tx_page_obj
    })