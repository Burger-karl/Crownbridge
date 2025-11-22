# payment/management/commands/mock_test_transfers.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from payment.models import UserBalance
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample transfers for QA (dev only).'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='from_email', required=True, help='Sender email')
        parser.add_argument('--to', dest='to_email', required=True, help='Recipient email')
        parser.add_argument('--amount', dest='amount', required=True, help='Amount to transfer')

    def handle(self, *args, **options):
        from_email = options['from_email']
        to_email = options['to_email']
        raw_amount = options['amount']

        try:
            amount = Decimal(raw_amount)
        except Exception:
            self.stdout.write(self.style.ERROR("Invalid amount"))
            return

        try:
            sender = User.objects.get(email=from_email)
            recipient = User.objects.get(email=to_email)
        except User.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f"User missing: {e}"))
            return

        sb, _ = UserBalance.objects.get_or_create(user=sender)
        rb, _ = UserBalance.objects.get_or_create(user=recipient)

        if (sb.balance or Decimal('0')) < amount:
            self.stdout.write(self.style.ERROR(f"Insufficient balance: {sb.balance} < {amount}"))
            return

        try:
            sb.transfer_to(recipient, amount, note='Mock transfer from management command')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Transfer failed: {e}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Transferred {amount} from {sender.email} to {recipient.email}"))
