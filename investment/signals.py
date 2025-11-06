from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import InvestmentPlan


@receiver(post_migrate)
def create_default_plans(sender, **kwargs):
    if sender.name == "investment":
        plans = [
            {
                "name": "Basic Plan",
                "profit_percent": 13,
                "duration_hours": 24,
                "min_deposit": 100,
                "max_deposit": 999,
                "referral_bonus_percent": None,
            },
            {
                "name": "Standard Plan",
                "profit_percent": 25,
                "duration_hours": 36,
                "min_deposit": 1000,
                "max_deposit": 4999,
                "referral_bonus_percent": None,
            },
            {
                "name": "Expert Plan",
                "profit_percent": 50,
                "duration_hours": 48,
                "min_deposit": 5000,
                "max_deposit": 10999,
                "referral_bonus_percent": None,
            },
            {
                "name": "VIP Plan",
                "profit_percent": 100,
                "duration_hours": 72,
                "min_deposit": 11000,
                "max_deposit": None,
                "referral_bonus_percent": 8,
            },
        ]

        for plan_data in plans:
            InvestmentPlan.objects.get_or_create(name=plan_data["name"], defaults=plan_data)



from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserInvestment
from users.models import CustomUser
from payment.models import UserBalance, Transaction
from decimal import Decimal

@receiver(post_save, sender=UserInvestment)
def credit_referral_on_investment(sender, instance: UserInvestment, created, **kwargs):
    if not created:
        return

    user = instance.user
    referrer = getattr(user, "referred_by", None)
    if not referrer:
        return

    # compute bonus: percent on the invested amount
    bonus_percent = getattr(referrer, "referral_bonus_percent", 8.0)
    try:
        percent = Decimal(bonus_percent) / Decimal(100)
        bonus_amount = (instance.amount_invested * percent).quantize(Decimal("0.01"))
    except Exception:
        return

    # credit the referrer internal balance and create a transaction
    ub, _ = UserBalance.objects.get_or_create(user=referrer)
    ub.credit(bonus_amount, note=f"Referral bonus from {user.email} investment {instance.id}")

    # Optionally record a Referral record (see below if you want)
