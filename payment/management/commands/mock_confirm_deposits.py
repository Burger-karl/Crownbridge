# payment/management/commands/mock_confirm_deposits.py
from django.core.management.base import BaseCommand
from payment.models import Deposit
from django.utils import timezone
from decimal import Decimal
from django.db import transaction
from payment.models import UserBalance
from investment.models import InvestmentIntent, UserInvestment
from datetime import timedelta

class Command(BaseCommand):
    help = "Mock confirm pending deposits created via invest flow and activate investments."

    def handle(self, *args, **options):
        pending = Deposit.objects.filter(status="pending")
        for d in pending:
            # mark deposit confirmed
            d.status = "confirmed"
            d.confirmations = 12
            d.save(update_fields=["status", "confirmations", "updated_at"])
            print(f"Confirmed deposit tx {d.tx_hash} for user {d.user}")

            # credit user balance
            ub, _ = UserBalance.objects.get_or_create(user=d.user)
            # Ensure amount as Decimal (Deposit.amount might have many decimals); convert down to 8 decimals
            amount = d.amount.quantize(Decimal('0.01')) if d.amount is not None else Decimal('0.00')
            ub.credit(amount, note=f"Deposit {d.tx_hash}", reference=d.tx_hash)

            # Find matching InvestmentIntent (by amount and user) and activate
            intent = InvestmentIntent.objects.filter(user=d.user, amount=amount, completed=False).first()
            if intent:
                # Create a UserInvestment record
                end_time = timezone.now() + timedelta(hours=intent.plan.duration_hours)
                ui = UserInvestment.objects.create(
                    user=d.user,
                    plan=intent.plan,
                    amount_invested=amount,
                    profit_earned=0,
                    start_time=timezone.now(),
                    end_time=end_time,
                    is_active=True
                )
                intent.completed = True
                intent.deposit_tx = d.tx_hash
                intent.save(update_fields=["completed", "deposit_tx"])
                print(f"Activated investment {ui.id} for user {d.user}")
