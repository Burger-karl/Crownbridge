from django.urls import path
from .views import guest_home_view, home_view, user_dashboard_view

urlpatterns = [
    path("", guest_home_view, name="guest_home"),
    path("home/", home_view, name="home"),
    path("portfolio/", user_dashboard_view, name="user_dashboard"),
]
