# from django.apps import AppConfig


# class NotificationsConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'notifications'


from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    name = "notifications"

    def ready(self):
        from .signals import kyc, withdrawal, deposit, investment, p2p
