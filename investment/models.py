import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

User = settings.AUTH_USER_MODEL


class InvestmentPlan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    profit_percent = models.DecimalField(max_digits=5, decimal_places=2)
    duration_hours = models.PositiveIntegerField()
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    max_deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    automated_payout = models.BooleanField(default=True)
    instant_withdrawal = models.BooleanField(default=True)
    referral_bonus_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Investment Plan"
        verbose_name_plural = "Investment Plans"

    def __str__(self):
        return f"{self.name} Plan"


class UserInvestment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.CASCADE, related_name='user_investments')
    amount_invested = models.DecimalField(max_digits=12, decimal_places=2)
    profit_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    auto_payout_done = models.BooleanField(default=False)

    class Meta:
        verbose_name = "User Investment"
        verbose_name_plural = "User Investments"
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.user} - {self.plan.name}"

    def calculate_expected_profit(self):
        return (self.amount_invested * self.plan.profit_percent) / 100


class InvestmentIntent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='investment_intents')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    chain = models.CharField(max_length=64, default='ethereum')
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    deposit_tx = models.CharField(max_length=128, blank=True, null=True)
