# payment/management/commands/seed_platform_wallets.py

from django.core.management.base import BaseCommand
from payment.models import PlatformWallet
from payment.constants import RECEIVER_ADDRESSES

WALLETS = [
    {"name": "Bitcoin",  "chain": "bitcoin",  "address": RECEIVER_ADDRESSES["bitcoin"]},
    {"name": "Ethereum", "chain": "ethereum", "address": RECEIVER_ADDRESSES["ethereum"]},
    {"name": "Tron",     "chain": "tron",     "address": RECEIVER_ADDRESSES["tron"]},
    {"name": "Solana",   "chain": "solana",   "address": RECEIVER_ADDRESSES["solana"]},
]

class Command(BaseCommand):
    help = "Seed platform wallets from constants.py"

    def handle(self, *args, **kwargs):
        for w in WALLETS:
            obj, created = PlatformWallet.objects.update_or_create(
                chain=w["chain"],
                defaults={"name": w["name"], "address": w["address"]},
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status}: {obj}")
        self.stdout.write(self.style.SUCCESS("Done."))