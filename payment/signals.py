from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserBalance, Deposit
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_balance(sender, instance, created, **kwargs):
    if created:
        UserBalance.objects.get_or_create(user=instance)


@receiver(post_save, sender=Deposit)
def credit_on_confirm(sender, instance: Deposit, created, **kwargs):
    """
    Credit the user's balance ONLY when:
      1. status == 'confirmed'   (blockchain confirmed)
      2. admin_approved == True  (admin has reviewed and approved)
      3. credited == False       (not already credited)

    This means a deposit goes through this flow:
      pending → confirmed (blockchain) → admin approves → balance credited
    """
    if (
        instance.status == "confirmed"
        and instance.admin_approved
        and not instance.credited
    ):
        ub, _ = UserBalance.objects.get_or_create(user=instance.user)
        ub.credit(
            instance.amount,
            note=f"Deposit {instance.tx_hash} approved",
            reference=str(instance.id),   # use UUID as reference to avoid tx_hash collision
        )
        instance.credited = True
        instance.save(update_fields=["credited"])