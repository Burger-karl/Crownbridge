from .models import Notification

def notifications_processor(request):
    if not request.user.is_authenticated:
        return {}

    # Base queryset (NOT sliced)
    qs = Notification.objects.filter(user=request.user)

    unread_count = qs.filter(is_read=False).count()

    # Slice ONLY for display
    latest_notifications = qs.order_by('-created_at')[:10]

    return {
        "notifications": latest_notifications,
        "notifications_unread_count": unread_count,
    }
