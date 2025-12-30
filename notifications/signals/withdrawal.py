from django.db.models.signals import post_save
from django.dispatch import receiver
from payment.models import WithdrawalRequest
from notifications.services import notify_user, notify_admins


@receiver(post_save, sender=WithdrawalRequest)
def withdrawal_notifications(sender, instance, created, **kwargs):
    if created:
        notify_admins(
            "New Withdrawal Request",
            f"{instance.user.email} requested withdrawal of {instance.amount}.",
            "withdrawal"
        )

    if instance.status == "approved":
        notify_user(
            instance.user,
            "Withdrawal Approved",
            "Your withdrawal request has been approved.",
            "withdrawal"
        )

    if instance.status == "rejected":
        notify_user(
            instance.user,
            "Withdrawal Declined",
            "Your withdrawal request was declined.",
            "withdrawal"
        )
