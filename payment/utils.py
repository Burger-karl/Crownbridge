# from payment.models import Deposit, WithdrawalRequest, Transaction, P2PTransfer

# from django.db import models

# def get_user_available_balance(user):
#     total_deposit = Deposit.objects.filter(
#         user=user, status="confirmed"
#     ).aggregate(total=models.Sum("amount"))["total"] or 0

#     total_withdrawn = WithdrawalRequest.objects.filter(
#         user=user, status="sent"
#     ).aggregate(total=models.Sum("amount"))["total"] or 0

#     total_transfers_sent = Transaction.objects.filter(
#         user=user, kind="debit"
#     ).aggregate(total=models.Sum("amount"))["total"] or 0

#     total_p2p_sent = P2PTransfer.objects.filter(
#         sender=user
#     ).aggregate(total=models.Sum("amount"))["total"] or 0

#     # FINAL BALANCE = deposits - withdrawals - transfers - p2p
#     return total_deposit - total_withdrawn - total_transfers_sent - total_p2p_sent


from decimal import Decimal
from payment.models import UserBalance

def get_user_available_balance(user):
    """
    Single source of truth for available balance.
    Reflects deposits, investments, withdrawals, transfers, and P2P.
    """
    ub, _ = UserBalance.objects.get_or_create(user=user)
    return ub.balance or Decimal("0")
