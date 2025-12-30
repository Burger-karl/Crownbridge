# payment/management/commands/mock_send_payouts.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from payment.models import WithdrawalRequest

class Command(BaseCommand):
    help = "Mock-send approved withdrawal payouts."

    def handle(self, *args, **kwargs):
        withdrawals = WithdrawalRequest.objects.filter(status="approved")

        if not withdrawals.exists():
            self.stdout.write(self.style.WARNING("No approved withdrawals found."))
            return

        for w in withdrawals:
            with transaction.atomic():
                if w.status != "approved":
                    continue

                w.status = "sent"
                w.tx_hash = f"MOCKTX_{w.id.hex[:12]}"
                w.processed_at = timezone.now()
                w.save(update_fields=["status", "tx_hash", "processed_at"])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Withdrawal {w.id} sent (mock tx: {w.tx_hash})"
                    )
                )
