from django.db.models.signals import post_save
from django.dispatch import receiver
from investment.models import UserInvestment
from notifications.services import notify_user, notify_admins


@receiver(post_save, sender=UserInvestment)
def investment_notifications(sender, instance, created, **kwargs):
    if created:
        notify_user(
            instance.user,
            "Investment Started",
            f"Your investment in {instance.plan.name} has started.",
            "investment"
        )

        notify_admins(
            "New Investment",
            f"{instance.user.email} invested {instance.amount_invested} in {instance.plan.name}.",
            "investment"
        )

    if not instance.is_active:
        notify_user(
            instance.user,
            "Investment Completed",
            f"Your investment in {instance.plan.name} has expired.",
            "investment"
        )
