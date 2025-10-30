# payment/management/commands/mock_send_payouts.py
from django.core.management.base import BaseCommand
from payment.models import WithdrawalRequest
from django.utils import timezone

class Command(BaseCommand):
    help = "Mock sending payouts for approved withdrawals."

    def handle(self, *args, **kwargs):
        approved = WithdrawalRequest.objects.filter(status="approved")
        for w in approved:
            # simulate sending: set status to 'sent' and tx_hash
            w.status = "sent"
            w.tx_hash = f"MOCKTX_{w.id.hex[:12]}"
            w.processed_at = timezone.now()
            w.save(update_fields=["status", "tx_hash", "processed_at"])
            self.stdout.write(self.style.SUCCESS(f"Sent payout for {w.id} tx {w.tx_hash}"))
