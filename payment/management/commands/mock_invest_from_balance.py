from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from payment.models import Deposit, UserBalance
from investment.models import InvestmentIntent, UserInvestment

class Command(BaseCommand):
    help = "Mock investment using internal user balance."

    def handle(self, *args, **kwargs):
        intents = InvestmentIntent.objects.filter(completed=False, use_balance=True)

        for intent in intents:
            with transaction.atomic():
                ub = UserBalance.objects.select_for_update().get(user=intent.user)

                if ub.balance < intent.amount:
                    self.stdout.write(self.style.ERROR(
                        f"Insufficient balance for {intent.user}"
                    ))
                    continue

                ub.debit(intent.amount, note="Internal balance investment")

                UserInvestment.objects.create(
                    user=intent.user,
                    plan=intent.plan,
                    amount_invested=intent.amount,
                    start_time=timezone.now(),
                    end_time=timezone.now() + timedelta(hours=intent.plan.duration_hours),
                    is_active=True
                )

                intent.completed = True
                intent.save(update_fields=["completed"])
