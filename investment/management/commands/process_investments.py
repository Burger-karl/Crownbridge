# investment/management/commands/process_investments.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from investment.models import UserInvestment
from payment.models import UserBalance
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Process investment accruals and finalize matured investments. Run regularly (eg: every 5-15 minutes)."

    def handle(self, *args, **options):
        now = timezone.now()
        # Process active investments
        active_qs = UserInvestment.objects.filter(is_active=True)
        stats = {"processed": 0, "materialized": Decimal("0.00"), "finalized": 0}
        for inv in active_qs.select_related('plan', 'user'):
            try:
                # materialize accrued profit (credits if automated payout)
                ub, _ = UserBalance.objects.get_or_create(user=inv.user)
                amount = inv.materialize_accrued(now, ub_instance=ub)
                if amount and amount > 0:
                    stats['materialized'] += Decimal(amount)
                    logger.info("Materialized %s for investment %s (user %s)", amount, inv.id, inv.user)

                # finalize if matured
                if now >= inv.end_time:
                    payments = inv.finalize(now, ub)
                    stats['finalized'] += 1
                    logger.info("Finalized investment %s: %s", inv.id, payments)
                stats['processed'] += 1

            except Exception as e:
                logger.exception("Error processing investment %s: %s", getattr(inv, 'id', '?'), e)

        self.stdout.write(self.style.SUCCESS("Processed investments: %s, materialized total: %s, finalized: %s" %
                                             (stats['processed'], stats['materialized'], stats['finalized'])))
