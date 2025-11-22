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

@login_required
def user_dashboard_view(request):
    """
    Displays user's investment dashboard with stats and KYC info.
    """

    user = request.user

    # --- INVESTMENTS ---
    investments = (
        UserInvestment.objects.filter(user=user)
        .select_related("plan")
        .order_by("-start_time")
    )
    intents = InvestmentIntent.objects.filter(user=user)
    intent_map = {i.plan_id: i.chain for i in intents}

    # --- DEPOSITS & WITHDRAWALS ---
    deposits = Deposit.objects.filter(user=user, status="confirmed")
    withdrawals = WithdrawalRequest.objects.filter(user=user)

    total_deposit = deposits.aggregate(total=models.Sum("amount"))["total"] or 0
    total_withdrawn = withdrawals.filter(status="sent").aggregate(total=models.Sum("amount"))["total"] or 0
    available_balance = total_deposit - total_withdrawn

    last_withdrawal = withdrawals.first()

    paginator = Paginator(investments, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # --- KYC STATUS ---
    kyc_verified = user.kyc_verified  # ✅ now directly from CustomUser

    referral_url = request.build_absolute_uri(user.referral_link)

    sent_transfers = P2PTransfer.objects.filter(sender=user)
    received_transfers = P2PTransfer.objects.filter(receiver=user)

    context = {
        "user": user,
        "page_obj": page_obj,
        "intent_map": intent_map,
        "available_balance": available_balance,
        "total_deposit": total_deposit,
        "total_withdrawn": total_withdrawn,
        "kyc_verified": kyc_verified,
        "last_withdrawal": last_withdrawal,
        "recent_withdrawals": withdrawals[:5],
        "referral_url": referral_url,
        "sent_transfers": sent_transfers,
        "received_transfers": received_transfers,

    }

    return render(request, "dashboard/user_dashboard.html", context)
