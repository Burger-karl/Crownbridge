# payment/models.py
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

    def credit(self, amount: Decimal, note: str = "", reference: str = None):
        Transaction.objects.create(user=self.user, amount=amount, kind='credit', note=note, reference=reference)
        # Ensure Decimal arithmetic
        self.balance = (self.balance or Decimal('0')) + Decimal(amount)
        self.save(update_fields=['balance', 'updated_at'])

    def debit(self, amount: Decimal, note: str = "", reference: str = None):
        amount = Decimal(amount)
        if (self.balance or Decimal('0')) < amount:
            raise ValueError("Insufficient balance")
        Transaction.objects.create(user=self.user, amount=amount, kind='debit', note=note, reference=reference)
        self.balance = (self.balance or Decimal('0')) - amount
        self.save(update_fields=['balance', 'updated_at'])

    def transfer_to(self, recipient_user, amount: Decimal, note: str = "Transfer"):
        """
        Atomically transfer `amount` from this user to recipient_user.
        Creates Transaction rows for both parties and updates balances.
        """
        amount = Decimal(amount)

        if self.user == recipient_user:
            raise ValueError("Cannot transfer to self")
        if amount <= Decimal('0'):
            raise ValueError("Transfer amount must be positive")

        # Use select_for_update to lock rows in a transaction
        with transaction.atomic():
            sender_balance = UserBalance.objects.select_for_update().get(pk=self.pk)
            receiver_balance, _ = UserBalance.objects.select_for_update().get_or_create(user=recipient_user)

            if (sender_balance.balance or Decimal('0')) < amount:
                raise ValueError("Insufficient balance")

            # record debit for sender
            Transaction.objects.create(
                user=self.user,
                amount=amount,
                kind='debit',
                note=note,
            )
            sender_balance.balance = sender_balance.balance - amount
            sender_balance.save(update_fields=['balance', 'updated_at'])

            # record credit for receiver
            Transaction.objects.create(
                user=recipient_user,
                amount=amount,
                kind='credit',
                note=f"Received transfer from {self.user}",
            )
            receiver_balance.balance = (receiver_balance.balance or Decimal('0')) + amount
            receiver_balance.save(update_fields=['balance', 'updated_at'])

            return sender_balance, receiver_balance


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
        ordering = ['-created_at']


class PlatformWallet(models.Model):
    CHAIN_CHOICES = [
        ("ethereum", "Ethereum (ERC20)"),
        ("bsc", "Binance Smart Chain (BEP20)"),
        ("tron", "Tron (TRC20)"),
        ("bitcoin", "Bitcoin (BTC)"),
        ("solana", "Solana (SOL)"),
        ("polygon", "Polygon (MATIC)"),
    ]

    name = models.CharField(max_length=50)
    chain = models.CharField(max_length=32, choices=CHAIN_CHOICES)
    xpub = models.TextField(blank=True, null=True, help_text="Extended public key to derive deposit addresses (no priv keys!)")
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
        unique_together = ("user", "platform_wallet")

    def __str__(self):
        return f"{self.user} -> {self.address or 'Pending...'} ({self.platform_wallet.chain})"

    def generate_address(self):
        """Simulate address generation (replace with real wallet API in production)."""
        self.address = f"{self.platform_wallet.chain}_{uuid.uuid4().hex[:20]}"
        self.save(update_fields=["address"])
        return self.address


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
    tx_hash = models.CharField(max_length=128, db_index=True)
    from_address = models.CharField(max_length=128, blank=True, null=True)
    token_contract = models.CharField(max_length=128, help_text="Token contract address (USDT)", null=True, blank=True)
    amount = models.DecimalField(max_digits=32, decimal_places=18, null=True, blank=True)
    amount_raw = models.DecimalField(max_digits=64, decimal_places=0, null=True, blank=True)
    confirmations = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    credited = models.BooleanField(default=False, help_text="Whether user's internal balance was credited")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tx_hash"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.user} deposit {self.amount} ({self.status})"


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
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_transfers")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_transfers")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.email} → {self.receiver.email} : {self.amount}"
