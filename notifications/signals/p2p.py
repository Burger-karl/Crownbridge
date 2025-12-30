from django.db.models.signals import post_save
from django.dispatch import receiver
from payment.models import P2PTransfer
from notifications.services import notify_user


@receiver(post_save, sender=P2PTransfer)
def p2p_notifications(sender, instance, **kwargs):
    if instance.status == "completed":
        notify_user(
            instance.receiver,
            "P2P Transfer Received",
            f"You received {instance.amount} {instance.chain.upper()} from {instance.sender.email}.",
            "p2p"
        )
