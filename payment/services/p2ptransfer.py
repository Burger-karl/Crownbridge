# payment/services/p2p.py
from django.db import transaction
from decimal import Decimal
from django.utils import timezone
from payment.models import UserBalance, P2PTransfer

def p2p_transfer(sender, receiver, amount, chain):
    amount = Decimal(amount)

    if sender == receiver:
        raise ValueError("Cannot send to yourself")

    with transaction.atomic():
        sender_balance = UserBalance.objects.select_for_update().get(user=sender)
        receiver_balance, _ = UserBalance.objects.select_for_update().get_or_create(user=receiver)

        if sender_balance.balance < amount:
            raise ValueError("Insufficient balance")

        # Debit sender
        sender_balance.debit(amount, note="P2P transfer")

        # Credit receiver
        receiver_balance.credit(amount, note=f"P2P received from {sender.email}")

        # Record transfer
        tx = P2PTransfer.objects.create(
            sender=sender,
            receiver=receiver,
            amount=amount,
            chain=chain,
            status="completed",
            completed_at=timezone.now()
        )

        return tx




# from django.db import transaction
# from payment.models import UserBalance, P2PTransfer

# def p2p_transfer(sender, receiver, amount, chain):
#     with transaction.atomic():
#         sender_balance = UserBalance.objects.select_for_update().get(user=sender)
#         receiver_balance = UserBalance.objects.select_for_update().get(user=receiver)

#         if sender_balance.balance < amount:
#             raise Exception("Insufficient balance")

#         sender_balance.debit(
#             amount,
#             note=f"P2P transfer to {receiver.email}"
#         )

#         receiver_balance.credit(
#             amount,
#             note=f"P2P transfer from {sender.email}"
#         )

#         P2PTransfer.objects.create(
#             sender=sender,
#             receiver=receiver,
#             amount=amount,
#             chain=chain
#         )
