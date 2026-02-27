# notifications/signals/kyc.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from kyc.models import KYCVerification
from notifications.services import notify_user, notify_admins


@receiver(post_save, sender=KYCVerification)
def kyc_notifications(sender, instance, created, **kwargs):
    if created:
        # New submission — alert all admins
        notify_admins(
            "New KYC Submission",
            f"{instance.user.email} submitted KYC details.",
            "kyc",
        )

    elif instance.status == KYCVerification.STATUS_APPROVED:
        notify_user(
            instance.user,
            "KYC Approved ✅",
            "Congratulations! Your identity has been verified. You now have full access.",
            "kyc",
        )

    elif instance.status == KYCVerification.STATUS_REJECTED:
        reason = instance.rejection_reason or "Please review your submission."
        notify_user(
            instance.user,
            "KYC Rejected ❌",
            f"Your KYC submission was not approved. Reason: {reason}. Please re-submit.",
            "kyc",
        )