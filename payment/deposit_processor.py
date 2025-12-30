from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from payment.models import Deposit, UserBalance
from investment.models import UserInvestment

def finalize_deposit(deposit: Deposit):
    """
    Called once a blockchain deposit is verified and confirmed.
    """

    with transaction.atomic():
        # Prevent double processing
        deposit = Deposit.objects.select_for_update().get(pk=deposit.pk)

        if deposit.status != "confirmed" or deposit.credited:
            return

        # Credit balance (your signal already does this)
        # Now check if linked to investment intent
        intent = getattr(deposit, "investment_intent", None)

        if intent and not intent.completed:
            plan = intent.plan
            amount = deposit.amount

            now = timezone.now()
            end_time = now + timedelta(hours=plan.duration_hours)

            # Deduct from balance immediately for investment
            ub = UserBalance.objects.select_for_update().get(user=deposit.user)
            ub.debit(
                amount,
                note=f"Investment into {plan.name}",
                reference=str(intent.id)
            )

            UserInvestment.objects.create(
                user=deposit.user,
                plan=plan,
                amount_invested=amount,
                profit_earned=Decimal("0"),
                start_time=now,
                end_time=end_time,
                is_active=True,
                auto_payout_done=False
            )

            intent.completed = True
            intent.save(update_fields=["completed"])
