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
    # when a deposit becomes confirmed and not yet credited, credit the user's balance
    if instance.status == 'confirmed' and not instance.credited:
        ub, _ = UserBalance.objects.get_or_create(user=instance.user)
        ub.credit(instance.amount, note=f"Deposit {instance.tx_hash}", reference=instance.tx_hash)
        instance.credited = True
        instance.save(update_fields=['credited'])