from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import InvestmentPlan, InvestmentIntent, UserInvestment
from payment.models import UserBalance


# ── InvestmentPlan ────────────────────────────────────────────────────────────

@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display  = ("name", "profit_percent", "duration_hours", "min_deposit", "max_deposit", "automated_payout")
    list_filter   = ("automated_payout", "instant_withdrawal")
    search_fields = ("name",)


# ── UserInvestment actions ────────────────────────────────────────────────────

@admin.action(description="✅ Activate selected investments")
def activate_investments(modeladmin, request, queryset):
    count = 0
    for inv in queryset.filter(is_active=False):
        inv.is_active = True
        inv.save(update_fields=["is_active"])
        count += 1
    messages.success(request, f"✅ {count} investment(s) activated.")


@admin.action(description="🔴 Deactivate selected investments")
def deactivate_investments(modeladmin, request, queryset):
    count = 0
    for inv in queryset.filter(is_active=True):
        inv.is_active = False
        inv.save(update_fields=["is_active"])
        count += 1
    messages.success(request, f"🔴 {count} investment(s) deactivated.")


@admin.action(description="💰 Pay out profit for selected investments (credit user balance)")
def payout_investments(modeladmin, request, queryset):
    """
    Manually trigger profit payout for selected investments.
    Credits profit to user balance and marks auto_payout_done = True.
    """
    paid = 0
    for inv in queryset.filter(auto_payout_done=False, is_active=True):
        try:
            profit = inv.calculate_expected_profit()
            ub, _  = UserBalance.objects.get_or_create(user=inv.user)
            ub.credit(
                profit,
                note=f"Investment profit — {inv.plan.name}",
                reference=f"inv_profit_{inv.id}",
            )
            inv.profit_earned    = profit
            inv.auto_payout_done = True
            inv.is_active        = False
            inv.save(update_fields=["profit_earned", "auto_payout_done", "is_active"])
            paid += 1
        except Exception as e:
            messages.error(request, f"Error paying out investment {inv.id}: {e}")

    if paid:
        messages.success(request, f"💰 {paid} investment(s) paid out and credited.")


@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display  = (
        "id", "user", "plan", "amount_invested", "profit_earned",
        "start_time", "end_time", "is_active", "auto_payout_done",
    )
    list_filter   = ("is_active", "auto_payout_done", "plan")
    search_fields = ("user__email",)
    readonly_fields = ("start_time",)
    actions       = [activate_investments, deactivate_investments, payout_investments]


# ── InvestmentIntent ──────────────────────────────────────────────────────────

@admin.register(InvestmentIntent)
class InvestmentIntentAdmin(admin.ModelAdmin):
    list_display  = ("id", "user", "plan", "amount", "chain", "created_at", "completed", "deposit_tx")
    list_filter   = ("completed", "chain")
    search_fields = ("user__email",)
    readonly_fields = ("id", "created_at")