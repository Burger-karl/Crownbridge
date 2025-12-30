from django.db.models.signals import post_save
from django.dispatch import receiver
from payment.models import Deposit
from notifications.services import notify_admins


@receiver(post_save, sender=Deposit)
def deposit_notifications(sender, instance, created, **kwargs):
    if created:
        notify_admins(
            "New Deposit Detected",
            f"{instance.user.email} deposited {instance.amount}.",
            "deposit"
        )
