import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import KYCVerification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=KYCVerification)
def sync_user_kyc_status(sender, instance: KYCVerification, created, **kwargs):
    """
    Keep CustomUser.kyc_verified in sync with KYCVerification.status.
    Called after every save on KYCVerification.
    """
    user = instance.user
    new_verified = instance.status == KYCVerification.STATUS_APPROVED

    if user.kyc_verified != new_verified:
        user.kyc_verified = new_verified
        user.save(update_fields=["kyc_verified"])
        logger.info(
            "kyc_verified updated to %s for user %s",
            new_verified,
            user.email,
        )