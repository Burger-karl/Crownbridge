from django.db.models.signals import post_save
from django.dispatch import receiver
from kyc.models import KYCVerification
from notifications.services import notify_user, notify_admins


@receiver(post_save, sender=KYCVerification)
def kyc_notifications(sender, instance, created, **kwargs):
    if created:
        notify_admins(
            "New KYC Submission",
            f"{instance.user.email} submitted KYC details.",
            "kyc"
        )

    if instance.verified:
        notify_user(
            instance.user,
            "KYC Approved",
            "Your KYC verification has been approved.",
            "kyc"
        )
