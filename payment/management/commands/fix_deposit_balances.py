from django.core.management.base import BaseCommand
from django.db import transaction

from payment.models import Deposit, UserBalance


class Command(BaseCommand):
    help = "Fix deposits approved but not credited"

    @transaction.atomic
    def handle(self, *args, **kwargs):

        deposits = Deposit.objects.select_for_update().filter(
            admin_approved=True,
            credited=False,
            status="confirmed",
        )

        fixed = 0

        for deposit in deposits:

            user_balance, _ = UserBalance.objects.get_or_create(
                user=deposit.user
            )

            user_balance.balance += deposit.amount
            user_balance.save(update_fields=["balance"])

            deposit.credited = True
            deposit.save(update_fields=["credited"])

            fixed += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Credited ${deposit.amount} to {deposit.user.email}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDONE: {fixed} deposits fixed."
            )
        )