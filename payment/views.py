# payment/views.py
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from uuid import uuid4
from users.models import CustomUser
from .forms import WithdrawalRequestForm, TransferForm, DepositForm
from .models import WithdrawalRequest, UserBalance, Transaction, Deposit, PlatformWallet, DepositAddress

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
def approve_withdrawal(request, wid):
    """
    Approve a pending withdrawal: debit user's balance immediately, mark as 'approved'.
    NOTE: Actual blockchain payout should happen in background (worker). Here we only mark.
    """
    wr = get_object_or_404(WithdrawalRequest, pk=wid)
    if wr.status != "pending":
        messages.error(request, "Withdrawal is not pending.")
        return redirect("payment:admin_pending_withdrawals")

    with transaction.atomic():
        ub, _ = UserBalance.objects.get_or_create(user=wr.user)
        # Check balance again
        if ub.balance < wr.amount:
            messages.error(request, f"User {wr.user} has insufficient balance — cannot approve.")
            return redirect("payment:admin_pending_withdrawals")

        # Debit and record transaction
        try:
            ub.debit(wr.amount, note=f"Withdrawal approved {wr.id}", reference=str(wr.id))
        except Exception as e:
            messages.error(request, f"Error debiting user balance: {e}")
            return redirect("payment:admin_pending_withdrawals")

        # Update withdrawal status
        wr.status = "approved"
        wr.processed_at = timezone.now()
        wr.admin_note = (wr.admin_note or "") + f"\nApproved by {request.user} at {wr.processed_at}"
        wr.save(update_fields=["status", "processed_at", "admin_note"])

    messages.success(request, f"Approved withdrawal {wr.id}. User will be paid by the payout service.")
    return redirect("payment:admin_pending_withdrawals")


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


@login_required
def withdrawal_payment_page(request, wid):
    """
    Placeholder page for user to view payment details after admin approval.
    In production this page would show tx details or trigger the payout flow.
    """
    wr = get_object_or_404(WithdrawalRequest, pk=wid, user=request.user)
    if wr.status != "approved":
        messages.error(request, "Withdrawal is not approved for payment.")
        return redirect("payment:withdrawals")

    # In a real system you'd display tx details or the actual broadcast status
    return render(request, "payment/withdrawal_payment.html", {"withdrawal": wr})




# -------------------------
# Deposit flows (Intent)
# -------------------------
@login_required
def deposit_page(request):

    profile = request.user.profile  # Get wallet IDs from user profile

    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            chain = form.cleaned_data['chain']

            pw = PlatformWallet.objects.filter(chain=chain).first()

            deposit_address = None
            if pw:
                da, _ = DepositAddress.objects.get_or_create(user=request.user, platform_wallet=pw)
                if not da.address:
                    da.generate_address()
                deposit_address = da

            pseudo = f"intent_{uuid4().hex}"
            deposit = Deposit.objects.create(
                user=request.user,
                platform_wallet=pw,
                deposit_address=(deposit_address if deposit_address else None),
                tx_hash=pseudo,
                amount=amount,
                status='pending',
                credited=False,
            )

            messages.success(request, 'Deposit intent created. Follow the instructions to send funds.')
            return redirect('payment:deposit_instructions', deposit_id=deposit.id)

    else:
        form = DepositForm(initial={'chain': 'ethereum'})

    # wallet addresses from profile
    wallet_addresses = {
        "Bitcoin (BTC)": profile.bitcoin_id,
        "Ethereum (ETH)": profile.ethereum_id,
        "USDT (TRC20)": profile.usdt_trc20_id,
        "Tron (TRX)": profile.tron_id,
        "Binance BEP20": profile.bep20_id,
    }

    return render(request, 'payment/deposit_page.html', {
        'form': form,
        'wallet_addresses': wallet_addresses,
    })


@login_required
def deposit_instructions(request, deposit_id):
    d = get_object_or_404(Deposit, pk=deposit_id, user=request.user)
    receiver_address = None
    if d.deposit_address and d.deposit_address.address:
        receiver_address = d.deposit_address.address
    elif d.platform_wallet:
        # fallback: show platform wallet name (not ideal in prod)
        receiver_address = d.platform_wallet.name
    context = {
        'deposit': d,
        'receiver_address': receiver_address,
    }
    return render(request, 'payment/deposit_instructions.html', context)


@login_required
def deposit_history(request):
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'payment/deposit_history.html', {'deposits': deposits})


# -------------------------
# Transfers (internal)
# -------------------------
@login_required
def transfer_page(request):
    """
    Transfer internal balance from logged in user to another user (by email or username).
    """
    if request.method == 'POST':
        form = TransferForm(request.POST)
        if form.is_valid():
            recipient_identifier = form.cleaned_data['recipient']
            amount = form.cleaned_data['amount']
            note = form.cleaned_data.get('note') or f"Transfer from {request.user}"

            # find recipient (by email then username)
            recipient = None
            try:
                recipient = CustomUser.objects.get(email=recipient_identifier)
            except Exception:
                try:
                    recipient = CustomUser.objects.get(username=recipient_identifier)
                except Exception:
                    messages.error(request, 'Recipient not found by email or username.')
                    return redirect('payment:transfer')

            if recipient == request.user:
                messages.error(request, 'You cannot transfer to yourself.')
                return redirect('payment:transfer')

            ub, _ = UserBalance.objects.get_or_create(user=request.user)
            try:
                ub.transfer_to(recipient, amount, note=note)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('payment:transfer')

            messages.success(request, f'Transferred {amount} to {recipient}.')
            return redirect('payment:transfer_history')
    else:
        form = TransferForm()

    user_balance = None
    try:
        ub, _ = UserBalance.objects.get_or_create(user=request.user)
        user_balance = f"{ub.balance:,.2f}"    # formatted balance
    except Exception:
        user_balance = "0.00"


    return render(request, 'payment/transfer_page.html', {'form': form, 'user_balance': user_balance})


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

@login_required
def p2p_transfer_view(request):
    user = request.user

    if request.method == "POST":
        form = P2PTransferForm(request.POST)
        if form.is_valid():
            receiver_email = form.cleaned_data['receiver_email']
            amount = form.cleaned_data['amount']

            # Get receiver
            try:
                receiver = CustomUser.objects.get(email=receiver_email)
            except CustomUser.DoesNotExist:
                messages.error(request, "Receiver not found.")
                return redirect("payment:transfer")

            if receiver == user:
                messages.error(request, "You cannot send money to yourself.")
                return redirect("payment:transfer")

            # Calculate sender’s available balance
            total_deposit = Deposit.objects.filter(user=user, status="confirmed").aggregate(models.Sum("amount"))["amount__sum"] or 0
            total_withdrawn = 0  # withdrawals already deducted before
            total_sent = P2PTransfer.objects.filter(sender=user).aggregate(models.Sum("amount"))["amount__sum"] or 0
            total_received = P2PTransfer.objects.filter(receiver=user).aggregate(models.Sum("amount"))["amount__sum"] or 0

            available_balance = (total_deposit + total_received) - (total_sent + total_withdrawn)

            if amount > available_balance:
                messages.error(request, "Insufficient balance.")
                return redirect("payment:transfer")

            # Record transfer
            P2PTransfer.objects.create(
                sender=user,
                receiver=receiver,
                amount=amount
            )

            messages.success(request, f"Successfully sent ${amount} to {receiver.email}.")
            return redirect("dashboard:user_dashboard")

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
