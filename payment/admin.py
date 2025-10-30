from django.contrib import admin
from .models import WithdrawalRequest, Transaction, UserBalance, PlatformWallet, Deposit, DepositAddress
from django.utils import timezone
from django.contrib import messages

# Register your models here.

@admin.action(description="Approve selected withdrawals (debit user and mark processing)")
def approve_withdrawals(modeladmin, request, queryset):
    for w in queryset.filter(status='pending'):
        try:
            ub = UserBalance.objects.get(user=w.user)
            # Check balance
            if ub.balance < w.amount:
                messages.error(request, f"User {w.user} has insufficient balance for withdrawal {w.id}")
                continue
            # Debit user's balance immediately (ledger)
            ub.debit(w.amount, note=f"Withdrawal approved {w.id}", reference=str(w.id))
            w.status = 'approved'
            w.processed_at = timezone.now()
            w.admin_note = (w.admin_note or "") + f"\nApproved by {request.user} at {w.processed_at}"
            w.save()
            messages.info(request, f"Approved withdrawal {w.id}")
            # NOTE: Signing and broadcasting tx must happen in a secure worker / custody provider
        except Exception as e:
            messages.error(request, f"Error approving {w.id}: {e}")

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'to_address', 'chain', 'status', 'requested_at', 'processed_at')
    actions = [approve_withdrawals]

