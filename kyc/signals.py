






























# kyc/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import KYCVerification
from users.models import CustomUser

@receiver(post_save, sender=KYCVerification)
def update_user_kyc_status(sender, instance: KYCVerification, created, **kwargs):
    user = instance.user
    if instance.verified and not user.kyc_verified:
        user.kyc_verified = True
        user.save(update_fields=['kyc_verified'])
