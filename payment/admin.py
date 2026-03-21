from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import (
    WithdrawalRequest, Transaction, UserBalance,
    PlatformWallet, Deposit, DepositAddress,
)


# ── Deposit admin actions ─────────────────────────────────────────────────────

@admin.action(description="✅ Approve selected deposits (credits user balance)")
def approve_deposits(modeladmin, request, queryset):
    """
    Approves confirmed deposits that haven't been credited yet.
    Sets admin_approved=True which triggers the signal to credit the user.
    """
    approved = 0
    skipped  = 0
    for deposit in queryset:
        if deposit.admin_approved:
            skipped += 1
            continue
        if deposit.status != "confirmed":
            messages.warning(
                request,
                f"Deposit {deposit.id} is not confirmed yet (status: {deposit.status}). Skipped."
            )
            skipped += 1
            continue

        deposit.admin_approved    = True
        deposit.admin_approved_by = request.user
        deposit.admin_approved_at = timezone.now()
        deposit.save(update_fields=["admin_approved", "admin_approved_by", "admin_approved_at"])
        # post_save signal fires here and credits the user
        approved += 1

    if approved:
        messages.success(request, f"✅ {approved} deposit(s) approved and balance credited.")
    if skipped:
        messages.info(request, f"{skipped} deposit(s) were skipped (already approved or not confirmed).")


@admin.action(description="❌ Reject selected deposits")
def reject_deposits(modeladmin, request, queryset):
    """Marks deposits as rejected so they never get credited."""
    rejected = 0
    for deposit in queryset:
        if deposit.credited:
            messages.warning(request, f"Deposit {deposit.id} already credited — cannot reject.")
            continue
        deposit.status     = "rejected"
        deposit.admin_note = (deposit.admin_note or "") + f"\nRejected by {request.user} at {timezone.now()}"
        deposit.save(update_fields=["status", "admin_note"])
        rejected += 1
    if rejected:
        messages.success(request, f"❌ {rejected} deposit(s) rejected.")


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "amount", "chain_display",
        "status", "admin_approved", "credited",
        "created_at", "admin_approved_at",
    )
    list_filter  = ("status", "admin_approved", "credited")
    search_fields = ("user__email", "tx_hash", "from_address")
    readonly_fields = (
        "id", "tx_hash", "from_address", "amount", "amount_raw",
        "confirmations", "created_at", "updated_at",
        "admin_approved_by", "admin_approved_at", "credited",
    )
    ordering = ("-created_at",)
    actions  = [approve_deposits, reject_deposits]

    fieldsets = (
        ("Deposit Info", {
            "fields": (
                "id", "user", "platform_wallet", "deposit_address",
                "tx_hash", "from_address", "amount", "amount_raw",
                "confirmations", "status", "credited",
            )
        }),
        ("Admin Approval", {
            "fields": (
                "admin_approved", "admin_approved_by",
                "admin_approved_at", "admin_note",
            ),
            "description": (
                "Set 'Admin approved' to True to credit the user's balance "
                "(only works when status is 'confirmed')."
            ),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def chain_display(self, obj):
        if obj.platform_wallet:
            return obj.platform_wallet.get_chain_display()
        return "—"
    chain_display.short_description = "Chain"

    def save_model(self, request, obj, form, change):
        """
        When admin manually ticks admin_approved in the detail form,
        also set admin_approved_by and admin_approved_at automatically.
        """
        if obj.admin_approved and not obj.admin_approved_by:
            obj.admin_approved_by = request.user
            obj.admin_approved_at = timezone.now()
        super().save_model(request, obj, form, change)


# ── Withdrawal admin ──────────────────────────────────────────────────────────

@admin.action(description="Approve selected withdrawals (debit user and mark processing)")
def approve_withdrawals(modeladmin, request, queryset):
    for w in queryset.filter(status="pending"):
        try:
            ub = UserBalance.objects.get(user=w.user)
            if ub.balance < w.amount:
                messages.error(request, f"User {w.user} has insufficient balance for withdrawal {w.id}")
                continue
            ub.debit(w.amount, note=f"Withdrawal approved {w.id}", reference=str(w.id))
            w.status       = "approved"
            w.processed_at = timezone.now()
            w.admin_note   = (w.admin_note or "") + f"\nApproved by {request.user} at {w.processed_at}"
            w.save()
            messages.info(request, f"Approved withdrawal {w.id}")
        except Exception as e:
            messages.error(request, f"Error approving {w.id}: {e}")


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display  = ("id", "user", "amount", "to_address", "chain", "status", "requested_at", "processed_at")
    list_filter   = ("status", "chain")
    search_fields = ("user__email", "to_address")
    actions       = [approve_withdrawals]


# ── Other models ──────────────────────────────────────────────────────────────

@admin.register(UserBalance)
class UserBalanceAdmin(admin.ModelAdmin):
    list_display  = ("user", "balance", "updated_at")
    search_fields = ("user__email",)
    readonly_fields = ("updated_at",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ("id", "user", "amount", "kind", "note", "reference", "created_at")
    list_filter   = ("kind",)
    search_fields = ("user__email", "reference")
    readonly_fields = ("id", "created_at")


@admin.register(PlatformWallet)
class PlatformWalletAdmin(admin.ModelAdmin):
    list_display  = ("name", "chain", "address", "provider", "created_at")
    list_filter   = ("chain",)


@admin.register(DepositAddress)
class DepositAddressAdmin(admin.ModelAdmin):
    list_display  = ("user", "platform_wallet", "address", "active", "created_at")
    list_filter   = ("active",)
    search_fields = ("user__email", "address")