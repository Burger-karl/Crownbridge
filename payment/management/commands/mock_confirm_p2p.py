# # payment/management/commands/mock_confirm_p2p.py
# from django.core.management.base import BaseCommand
# from django.db import transaction
# from django.utils import timezone

# from payment.models import P2PTransfer

# class Command(BaseCommand):
#     help = "Mock confirm pending P2P transfers."

#     def handle(self, *args, **kwargs):
#         pending = P2PTransfer.objects.filter(status="pending")

#         if not pending.exists():
#             self.stdout.write(self.style.WARNING("No pending P2P transfers found."))
#             return

#         for tx in pending:
#             with transaction.atomic():
#                 tx.status = "completed"
#                 tx.completed_at = timezone.now()
#                 tx.save(update_fields=["status", "completed_at"])

#                 self.stdout.write(
#                     self.style.SUCCESS(f"P2P transfer {tx.id} completed")
#                 )



# payment/management/commands/mock_confirm_p2p.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from payment.models import P2PTransfer

class Command(BaseCommand):
    help = "Mock confirm pending P2P transfers."

    def handle(self, *args, **kwargs):
        pending = P2PTransfer.objects.filter(status="pending")

        for tx in pending:
            tx.status = "completed"
            tx.completed_at = timezone.now()
            tx.save(update_fields=["status", "completed_at"])

            self.stdout.write(
                self.style.SUCCESS(f"P2P transfer {tx.id} completed")
            )
