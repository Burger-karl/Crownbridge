from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from investment.models import InvestmentPlan
from payment.models import WithdrawalRequest

def guest_home_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    plans = InvestmentPlan.objects.all().order_by("min_deposit")

    successful_withdrawals = WithdrawalRequest.objects.filter(status="sent").select_related("user").order_by("-created_at")
    paginator = Paginator(successful_withdrawals, 7)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "dashboard/guest_home.html", {
        "plans": plans,
        "page_obj": page_obj,
    })


@login_required
def home_view(request):
    plans = InvestmentPlan.objects.all().order_by("min_deposit")

    successful_withdrawals = WithdrawalRequest.objects.filter(status="sent").select_related("user").order_by("-created_at")
    paginator = Paginator(successful_withdrawals, 7)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "dashboard/home.html", {
        "plans": plans,
        "page_obj": page_obj,
    })


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import models
from django.utils import timezone
from investment.models import UserInvestment, InvestmentIntent
from payment.models import WithdrawalRequest, Deposit, P2PTransfer

# @login_required
# def user_dashboard_view(request):
#     """
#     Displays user's investment dashboard with stats and KYC info.
#     """

#     user = request.user

#     # --- INVESTMENTS ---
#     investments = (
#         UserInvestment.objects.filter(user=user)
#         .select_related("plan")
#         .order_by("-start_time")
#     )
#     intents = InvestmentIntent.objects.filter(user=user)
#     intent_map = {i.plan_id: i.chain for i in intents}

#     # --- DEPOSITS & WITHDRAWALS ---
#     deposits = Deposit.objects.filter(user=user, status="confirmed")
#     withdrawals = WithdrawalRequest.objects.filter(user=user)

#     total_deposit = deposits.aggregate(total=models.Sum("amount"))["total"] or 0
#     total_withdrawn = withdrawals.filter(status="sent").aggregate(total=models.Sum("amount"))["total"] or 0
#     available_balance = total_deposit - total_withdrawn

#     last_withdrawal = withdrawals.first()

#     paginator = Paginator(investments, 10)
#     page_number = request.GET.get("page")
#     page_obj = paginator.get_page(page_number)

#     # --- KYC STATUS ---
#     kyc_verified = user.kyc_verified  # ✅ now directly from CustomUser

#     referral_url = request.build_absolute_uri(user.referral_link)

#     sent_transfers = P2PTransfer.objects.filter(sender=user)
#     received_transfers = P2PTransfer.objects.filter(receiver=user)

#     context = {
#         "user": user,
#         "page_obj": page_obj,
#         "intent_map": intent_map,
#         "available_balance": available_balance,
#         "total_deposit": total_deposit,
#         "total_withdrawn": total_withdrawn,
#         "kyc_verified": kyc_verified,
#         "last_withdrawal": last_withdrawal,
#         "recent_withdrawals": withdrawals[:5],
#         "referral_url": referral_url,
#         "sent_transfers": sent_transfers,
#         "received_transfers": received_transfers,

#     }

#     return render(request, "dashboard/user_dashboard.html", context)



from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, F
from investment.models import UserInvestment, InvestmentIntent
from payment.models import WithdrawalRequest, Deposit, Transaction, P2PTransfer
from payment.utils import get_user_available_balance

@login_required
def user_dashboard_view(request):
    
    user = request.user

    # --- Investments ---
    investments = UserInvestment.objects.filter(user=user, is_active=True).select_related("plan")

    # Calculate progress for each active investment
    for inv in investments:
        start = inv.start_time.timestamp()
        end = inv.end_time.timestamp()
        now = timezone.now().timestamp()

        if now <= start:
            progress = 0
        elif now >= end:
            progress = 100
        else:
            progress = ((now - start) / (end - start)) * 100

        inv.progress_percent = round(progress, 2)

    # --- Total Profit ---
    total_profit = sum(inv.calculate_expected_profit() for inv in investments)

    # --- DEPOSITS & WITHDRAWALS ---
    deposits = Deposit.objects.filter(user=user, status="confirmed")
    withdrawals = WithdrawalRequest.objects.filter(user=user)
    total_deposit = deposits.aggregate(total=Sum("amount"))["total"] or 0
    total_withdrawn = withdrawals.filter(status="sent").aggregate(total=Sum("amount"))["total"] or 0
    available_balance = get_user_available_balance(user)


    # --- Transactions (history) ---
    deposit_txs = deposits.annotate(tx_type=models.Value("Deposit", output_field=models.CharField()))
    withdrawal_txs = withdrawals.annotate(tx_type=models.Value("Withdrawal", output_field=models.CharField()))
    transfer_txs = Transaction.objects.filter(user=user).annotate(tx_type=models.Value("Transfer", output_field=models.CharField()))
    p2p_sent = P2PTransfer.objects.filter(sender=user).annotate(tx_type=models.Value("P2P Sent", output_field=models.CharField()))
    p2p_received = P2PTransfer.objects.filter(receiver=user).annotate(tx_type=models.Value("P2P Received", output_field=models.CharField()))

    # Merge all transactions & sort by date
    all_txs = list(deposit_txs) + list(withdrawal_txs) + list(transfer_txs) + list(p2p_sent) + list(p2p_received)
    all_txs.sort(key=lambda x: getattr(x, 'created_at', getattr(x, 'processed_at', None)), reverse=True)

    # --- Pagination ---
    paginator = Paginator(all_txs, 10)
    page_number = request.GET.get("page")
    tx_page_obj = paginator.get_page(page_number)

    # --- KYC & referral ---
    kyc_verified = user.kyc_verified
    referral_url = request.build_absolute_uri(user.referral_link)

    context = {
        "user": user,
        "investments": investments,
        "available_balance": available_balance,
        "total_deposit": total_deposit,
        "total_withdrawn": total_withdrawn,
        "total_profit": total_profit,
        "tx_page_obj": tx_page_obj,
        "kyc_verified": kyc_verified,
        "referral_url": referral_url,
    }
    return render(request, "dashboard/user_dashboard.html", context)


from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from kyc.models import KYCVerification
from payment.models import WithdrawalRequest

User = get_user_model()

@staff_member_required
def admin_dashboard_view(request):
    active_users_count = User.objects.filter(is_active=True).count()

    pending_kyc_count = KYCVerification.objects.filter(
        verified=False
    ).count()

    pending_withdrawals_count = WithdrawalRequest.objects.filter(
        status="pending"
    ).count()

    context = {
        "active_users_count": active_users_count,
        "pending_kyc_count": pending_kyc_count,
        "pending_withdrawals_count": pending_withdrawals_count,
    }
    return render(request, "dashboard/admin_dashboard.html", context)
