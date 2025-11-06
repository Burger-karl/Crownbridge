from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class KYCVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc")
    id_document = models.FileField(upload_to="kyc_docs/")
    selfie = models.ImageField(upload_to="kyc_selfies/")
    verified = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"KYC - {self.user.email} ({'Verified' if self.verified else 'Pending'})"
