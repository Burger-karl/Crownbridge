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


# dashboard/views.py
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from investment.models import UserInvestment, InvestmentIntent
from payment.models import WithdrawalRequest
from django.db import models

@login_required
def user_dashboard_view(request):
    """
    Displays user's investments and withdrawal statistics.
    """
    # Investments
    investments = (
        UserInvestment.objects.filter(user=request.user)
        .select_related("plan")
        .order_by("-start_time")
    )
    intents = InvestmentIntent.objects.filter(user=request.user)
    intent_map = {i.plan_id: i.chain for i in intents}

    # Withdrawals
    withdrawals = WithdrawalRequest.objects.filter(user=request.user).order_by("-created_at")
    total_withdrawn = withdrawals.filter(status="sent").aggregate(models.Sum("amount"))["amount__sum"] or 0
    last_withdrawal = withdrawals.first()

    paginator = Paginator(investments, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "user": request.user,
        "page_obj": page_obj,
        "intent_map": intent_map,
        "total_withdrawn": total_withdrawn,
        "last_withdrawal": last_withdrawal,
        "recent_withdrawals": withdrawals[:5],
    }
    return render(request, "dashboard/user_dashboard.html", context)
