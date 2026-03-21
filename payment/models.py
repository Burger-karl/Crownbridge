import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class UserBalance(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='balance')
    balance = models.DecimalField(max_digits=32, decimal_places=8, default=Decimal('0.0'))
    updated_at = models.DateTimeField(auto_now=True)

    def has_reference(self, reference: str) -> bool:
        if not reference:
            return False
        return Transaction.objects.filter(
            user=self.user,
            reference=reference
        ).exists()

    def credit(self, amount: Decimal, note: str = "", reference: str = None):
        Transaction.objects.create(
            user=self.user,
            amount=amount,
            kind='credit',
            note=note,
            reference=reference
        )
        self.balance = (self.balance or Decimal('0')) + Decimal(amount)
        self.save(update_fields=['balance', 'updated_at'])

    def debit(self, amount: Decimal, note: str = "", reference: str = None):
        amount = Decimal(amount)
        if (self.balance or Decimal('0')) < amount:
            raise ValueError("Insufficient balance")

        Transaction.objects.create(
            user=self.user,
            amount=amount,
            kind='debit',
            note=note,
            reference=reference
        )
        self.balance = (self.balance or Decimal('0')) - amount
        self.save(update_fields=['balance', 'updated_at'])


class Transaction(models.Model):
    KIND = [('credit', 'Credit'), ('debit', 'Debit')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    kind = models.CharField(max_length=10, choices=KIND)
    note = models.TextField(blank=True, null=True)
    reference = models.CharField(max_length=256, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "reference"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "reference"],
                condition=~models.Q(reference=None),
                name="unique_tx_reference_per_user"
            )
        ]


class PlatformWallet(models.Model):
    CHAIN_CHOICES = [
        ("ethereum", "Ethereum (ERC20)"),
        ("bsc", "Binance Smart Chain (BEP20)"),
        ("tron", "Tron (TRC20)"),
        ("bitcoin", "Bitcoin (BTC)"),
        ("solana", "Solana (SOL)"),
        ("polygon", "Polygon (MATIC)"),
    ]

    address = models.CharField(max_length=128, blank=True, null=True)
    name = models.CharField(max_length=50)
    chain = models.CharField(max_length=32, choices=CHAIN_CHOICES)
    xpub = models.TextField(blank=True, null=True)
    provider = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.chain})"


class DepositAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposit_addresses")
    platform_wallet = models.ForeignKey(PlatformWallet, on_delete=models.CASCADE, related_name="deposit_addresses")
    address = models.CharField(max_length=128, db_index=True, blank=True, null=True)
    derivation_index = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = (("user", "platform_wallet"),)

    def __str__(self):
        return f"{self.user} -> {self.address or 'Pending...'} ({self.platform_wallet.chain})"


class Deposit(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposits")
    platform_wallet = models.ForeignKey(PlatformWallet, on_delete=models.SET_NULL, null=True)
    deposit_address = models.ForeignKey(DepositAddress, on_delete=models.SET_NULL, null=True, blank=True)
    tx_hash = models.CharField(max_length=128, db_index=True, unique=True)
    from_address = models.CharField(max_length=128, blank=True, null=True)
    token_contract = models.CharField(max_length=128, null=True, blank=True)
    amount = models.DecimalField(max_digits=32, decimal_places=18, null=True, blank=True)
    amount_raw = models.DecimalField(max_digits=64, decimal_places=0, null=True, blank=True)
    confirmations = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    credited = models.BooleanField(default=False)

    admin_approved = models.BooleanField(
        default=False,
        help_text="Admin must approve this deposit before it is credited to the user's balance."
    )
    admin_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_deposits",
        help_text="Staff member who approved this deposit."
    )
    admin_approved_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    investment_intent = models.ForeignKey(
        "investment.InvestmentIntent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        indexes = [models.Index(fields=["tx_hash"]), models.Index(fields=["status"])]

    def __str__(self):
        approved = "✓ approved" if self.admin_approved else "⏳ awaiting approval"
        return f"{self.user} deposit {self.amount} ({self.status} / {approved})"


class WithdrawalRequest(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("processing", "Processing"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawals")
    amount = models.DecimalField(max_digits=32, decimal_places=18)
    to_address = models.CharField(max_length=128)
    chain = models.CharField(max_length=32, choices=PlatformWallet.CHAIN_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    admin_note = models.TextField(blank=True, null=True)
    tx_hash = models.CharField(max_length=128, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdrawal {self.amount} {self.chain} for {self.user} ({self.status})"


class P2PTransfer(models.Model):
    CHAIN_CHOICES = [
        ("tron", "TRON"),
        ("usdt_trc20", "USDT (TRC20)"),
        ("ethereum", "Ethereum (ETH)"),
        ("usdt_erc20", "USDT (ERC20)"),
        ("bitcoin", "Bitcoin (BTC)"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_p2p")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_p2p")
    amount = models.DecimalField(max_digits=18, decimal_places=8)
    chain = models.CharField(max_length=20, choices=CHAIN_CHOICES, default="tron")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"P2P {self.amount} {self.chain} from {self.sender} → {self.receiver}"