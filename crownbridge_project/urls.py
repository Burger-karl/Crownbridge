from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('users.urls')),
    path('', include("dashboard.urls")),
    path('investment/', include('investment.urls')),
    path('payment/', include('payment.urls')),
    path('kyc/', include('kyc.urls')),
    path('support/', include('supportchat.urls')),
    path('notify/', include('notifications.urls')),

]

# Media files in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
