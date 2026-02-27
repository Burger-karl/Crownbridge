
from django.db import models
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField

User = get_user_model()


class KYCVerification(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc")
    full_name = models.CharField(max_length=255, blank=True)
    id_document = CloudinaryField(resource_type="raw")
    selfie = CloudinaryField(resource_type="image")

    # Status replaces the plain boolean — gives admin more control
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Keep the legacy boolean field but derive it from status for backward compatibility
    verified = models.BooleanField(default=False)

    # Admin review fields
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kyc_reviews",
        help_text="Admin who last reviewed this KYC submission",
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason shown to the user when their KYC is rejected",
    )
    admin_notes = models.TextField(
        blank=True,
        help_text="Internal notes (not shown to user)",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "KYC Verification"
        verbose_name_plural = "KYC Verifications"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"KYC – {self.user.email} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def is_rejected(self):
        return self.status == self.STATUS_REJECTED

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING