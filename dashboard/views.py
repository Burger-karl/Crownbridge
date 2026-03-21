from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone

from investment.models import InvestmentPlan, UserInvestment, InvestmentIntent
from payment.models import WithdrawalRequest, Deposit, Transaction, P2PTransfer, UserBalance
from payment.utils import get_user_available_balance
from django.contrib.auth import get_user_model
from kyc.models import KYCVerification

User = get_user_model()


# ── public / guest ────────────────────────────────────────────────────────────

def guest_home_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    plans = InvestmentPlan.objects.all().order_by("min_deposit")
    successful_withdrawals = (
        WithdrawalRequest.objects.filter(status="sent")
        .select_related("user").order_by("-created_at")
    )
    paginator = Paginator(successful_withdrawals, 7)
    page_obj  = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/guest_home.html", {"plans": plans, "page_obj": page_obj})


@login_required
def home_view(request):
    plans = InvestmentPlan.objects.all().order_by("min_deposit")
    successful_withdrawals = (
        WithdrawalRequest.objects.filter(status="sent")
        .select_related("user").order_by("-created_at")
    )
    paginator = Paginator(successful_withdrawals, 7)
    page_obj  = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/home.html", {"plans": plans, "page_obj": page_obj})


# ── user dashboard ────────────────────────────────────────────────────────────

@login_required
def user_dashboard_view(request):
    user = request.user
    investments = (
        UserInvestment.objects.filter(user=user, is_active=True).select_related("plan")
    )
    for inv in investments:
        start = inv.start_time.timestamp()
        end   = inv.end_time.timestamp()
        now   = timezone.now().timestamp()
        if now <= start:   progress = 0
        elif now >= end:   progress = 100
        else:              progress = ((now - start) / (end - start)) * 100
        inv.progress_percent = round(progress, 2)

    total_profit      = sum(inv.calculate_expected_profit() for inv in investments)
    approved_deposits = Deposit.objects.filter(user=user, status="confirmed", admin_approved=True)
    withdrawals       = WithdrawalRequest.objects.filter(user=user)
    total_deposit     = approved_deposits.aggregate(total=Sum("amount"))["total"] or 0
    total_withdrawn   = withdrawals.filter(status="sent").aggregate(total=Sum("amount"))["total"] or 0
    available_balance = get_user_available_balance(user)
    pending_deposit_count = Deposit.objects.filter(
        user=user, admin_approved=False
    ).exclude(status="rejected").count()

    deposit_txs    = approved_deposits.annotate(tx_type=models.Value("Deposit",      output_field=models.CharField()))
    withdrawal_txs = withdrawals.annotate(tx_type=models.Value("Withdrawal",         output_field=models.CharField()))
    transfer_txs   = Transaction.objects.filter(user=user).annotate(tx_type=models.Value("Transfer",     output_field=models.CharField()))
    p2p_sent       = P2PTransfer.objects.filter(sender=user).annotate(tx_type=models.Value("P2P Sent",      output_field=models.CharField()))
    p2p_received   = P2PTransfer.objects.filter(receiver=user).annotate(tx_type=models.Value("P2P Received", output_field=models.CharField()))

    all_txs = list(deposit_txs) + list(withdrawal_txs) + list(transfer_txs) + list(p2p_sent) + list(p2p_received)
    all_txs.sort(key=lambda x: getattr(x, "created_at", None) or getattr(x, "processed_at", None), reverse=True)

    paginator   = Paginator(all_txs, 10)
    tx_page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "dashboard/user_dashboard.html", {
        "user":                  user,
        "investments":           investments,
        "available_balance":     available_balance,
        "total_deposit":         total_deposit,
        "total_withdrawn":       total_withdrawn,
        "total_profit":          total_profit,
        "tx_page_obj":           tx_page_obj,
        "kyc_verified":          user.kyc_verified,
        "referral_url":          request.build_absolute_uri(user.referral_link),
        "pending_deposit_count": pending_deposit_count,
    })


# ── admin dashboard ───────────────────────────────────────────────────────────

@staff_member_required
def admin_dashboard_view(request):
    return render(request, "dashboard/admin_dashboard.html", {
        "active_users_count":        User.objects.filter(is_active=True).count(),
        "pending_kyc_count":         KYCVerification.objects.filter(verified=False).count(),
        "pending_withdrawals_count": WithdrawalRequest.objects.filter(status="pending").count(),
        "pending_deposits_count":    Deposit.objects.filter(admin_approved=False).exclude(status="rejected").count(),
        "total_users_count":         User.objects.count(),
    })


# ── admin: user list ──────────────────────────────────────────────────────────

@staff_member_required
def admin_users_list(request):
    """Searchable, paginated list of all users."""
    query = request.GET.get("q", "").strip()
    users_qs = User.objects.select_related("profile").order_by("-date_joined")
    if query:
        users_qs = users_qs.filter(
            Q(email__icontains=query) | Q(full_name__icontains=query)
        )
    paginator = Paginator(users_qs, 25)
    page_obj  = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin_users_list.html", {
        "page_obj": page_obj,
        "query":    query,
        "total":    users_qs.count(),
    })


# ── admin: user detail ────────────────────────────────────────────────────────

@staff_member_required
def admin_user_detail(request, user_id):
    """Full detail view: profile, wallets, balance, investments, deposits, withdrawals."""
    target_user = get_object_or_404(User, pk=user_id)
    profile     = getattr(target_user, "profile", None)

    try:
        balance = UserBalance.objects.get(user=target_user).balance
    except UserBalance.DoesNotExist:
        balance = 0

    investments = UserInvestment.objects.filter(user=target_user).select_related("plan").order_by("-start_time")
    deposits    = Deposit.objects.filter(user=target_user).order_by("-created_at")
    withdrawals = WithdrawalRequest.objects.filter(user=target_user).order_by("-requested_at")

    try:
        kyc = KYCVerification.objects.get(user=target_user)
    except KYCVerification.DoesNotExist:
        kyc = None

    return render(request, "dashboard/admin_user_detail.html", {
        "target_user": target_user,
        "profile":     profile,
        "balance":     balance,
        "investments": investments,
        "deposits":    deposits,
        "withdrawals": withdrawals,
        "kyc":         kyc,
    })


# ── admin: toggle active ──────────────────────────────────────────────────────

@staff_member_required
def admin_toggle_user_active(request, user_id):
    """Enable or disable a user account."""
    target_user = get_object_or_404(User, pk=user_id)

    if target_user == request.user:
        messages.error(request, "You cannot disable your own account.")
        return redirect("admin_user_detail", user_id=user_id)

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=["is_active"])
    status = "enabled" if target_user.is_active else "disabled"
    messages.success(request, f"Account for {target_user.email} has been {status}.")
    return redirect("admin_user_detail", user_id=user_id)


# ── admin: delete user ────────────────────────────────────────────────────────

@staff_member_required
def admin_delete_user(request, user_id):
    """Permanently delete a user and all related data. Requires POST confirmation."""
    target_user = get_object_or_404(User, pk=user_id)

    if target_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect("admin_user_detail", user_id=user_id)

    if request.method == "POST":
        email = target_user.email
        target_user.delete()
        messages.success(request, f"User {email} has been permanently deleted.")
        return redirect("admin_users_list")

    return render(request, "dashboard/admin_user_delete_confirm.html", {
        "target_user": target_user,
    })