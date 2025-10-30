# payment/views.py
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

from .forms import WithdrawalRequestForm
from .models import WithdrawalRequest, UserBalance, Transaction

# helper
def is_staff(user):
    return user.is_staff

@login_required
def withdraw_page(request):
    """
    Show withdrawal form displaying user's invested totals and profit summary.
    On POST create WithdrawalRequest with status 'pending' and notify user.
    """
    # calculate totals (you might want to refine to separate profit vs principal)
    # We'll compute 'total_invested' and 'total_profit' from UserInvestment if available
    try:
        from investment.models import UserInvestment
        investments = UserInvestment.objects.filter(user=request.user)
        total_invested = sum((inv.amount_invested for inv in investments), Decimal('0.00'))
        # expected profit sum (calculated)
        total_expected_profit = sum((inv.calculate_expected_profit() for inv in investments), Decimal('0.00'))
    except Exception:
        total_invested = Decimal('0.00')
        total_expected_profit = Decimal('0.00')

    # user balance available for withdrawal
    ub, _ = UserBalance.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = WithdrawalRequestForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            to_address = form.cleaned_data["to_address"]
            chain = form.cleaned_data["chain"]

            # basic validations
            if amount <= Decimal("0.0"):
                messages.error(request, "Enter a valid amount.")
                return redirect("payment:withdraw")

            if ub.balance < amount:
                messages.error(request, "Insufficient balance for withdrawal.")
                return redirect("payment:withdraw")

            # create withdrawal request (pending)
            wr = WithdrawalRequest.objects.create(
                user=request.user,
                amount=amount,
                to_address=to_address,
                chain=chain,
                status="pending",
            )
            messages.success(request, "Withdrawal submitted — processing. Await admin approval.")
            return redirect("payment:withdrawals")
    else:
        form = WithdrawalRequestForm(initial={"chain": "ethereum"})

    context = {
        "form": form,
        "total_invested": total_invested,
        "total_expected_profit": total_expected_profit,
        "user_balance": ub.balance,
    }
    return render(request, "payment/withdrawal_request.html", context)


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
