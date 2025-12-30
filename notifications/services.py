from .models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()


def notify_user(user, title, message, notification_type="system"):
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type
    )


def notify_admins(title, message, notification_type="system"):
    admins = User.objects.filter(is_staff=True)
    Notification.objects.bulk_create([
        Notification(
            user=admin,
            title=title,
            message=message,
            notification_type=notification_type
        )
        for admin in admins
    ])
