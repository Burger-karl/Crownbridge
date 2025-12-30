# payment/management/commands/mock_confirm_deposits.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from payment.models import Deposit, UserBalance
from investment.models import InvestmentIntent, UserInvestment

class Command(BaseCommand):
    help = "Mock-confirm pending deposits and activate linked investments safely."

    def handle(self, *args, **options):
        deposits = Deposit.objects.filter(status="pending")

        if not deposits.exists():
            self.stdout.write(self.style.WARNING("No pending deposits found."))
            return

        for deposit in deposits:
            with transaction.atomic():
                if deposit.status != "pending":
                    continue  # idempotency protection

                # 1. Confirm deposit
                deposit.status = "confirmed"
                deposit.confirmations = 12
                deposit.updated_at = timezone.now()
                deposit.save(update_fields=["status", "confirmations", "updated_at"])

                # 2. Credit user balance
                ub, _ = UserBalance.objects.get_or_create(user=deposit.user)
                amount = deposit.amount.quantize(Decimal("0.01"))

                if not ub.has_reference(deposit.tx_hash):
                    ub.credit(
                        amount=amount,
                        note="Mock deposit confirmation",
                        reference=deposit.tx_hash
                    )

                # 3. Activate matching investment intent
                intent = InvestmentIntent.objects.filter(
                    user=deposit.user,
                    completed=False,
                    deposit_tx__isnull=True,
                    amount=amount
                ).select_for_update().first()

                if intent:
                    end_time = timezone.now() + timedelta(hours=intent.plan.duration_hours)

                    UserInvestment.objects.create(
                        user=deposit.user,
                        plan=intent.plan,
                        amount_invested=amount,
                        start_time=timezone.now(),
                        end_time=end_time,
                        is_active=True
                    )

                    intent.completed = True
                    intent.deposit_tx = deposit.tx_hash
                    intent.save(update_fields=["completed", "deposit_tx"])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Confirmed deposit {deposit.tx_hash} for {deposit.user.email}"
                    )
                )
