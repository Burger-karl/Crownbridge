import uuid
import random
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from .managers import CustomUserManager
from django.urls import reverse


def generate_referral_code():
    """Create short unique referral code — adapt length if you want."""
    return uuid.uuid4().hex[:10].upper()


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    is_verified = models.BooleanField(default=False)        # email OTP verified
    kyc_verified = models.BooleanField(default=False)       # KYC status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    # referral fields
    referral_code = models.CharField(max_length=32, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="referrals")
    referral_bonus_percent = models.DecimalField(max_digits=5, decimal_places=2, default=8.00)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.referral_code:
            # ensure unique: try a few times
            for _ in range(5):
                code = generate_referral_code()
                if not CustomUser.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
            if not self.referral_code:
                self.referral_code = f"REF{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def referral_link(self):
        # Change the domain/path to your real registration URL
        return f"{reverse('register')}?ref={self.referral_code}"


class EmailVerification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="verifications")
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expires_at

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))  # 6-digit OTP
