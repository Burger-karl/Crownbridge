from django.urls import path
from .views import (
    guest_home_view, home_view,
    user_dashboard_view, admin_dashboard_view,
    admin_users_list, admin_user_detail,
    admin_toggle_user_active, admin_delete_user,
)

urlpatterns = [
    path("",                 guest_home_view,     name="guest_home"),
    path("home/",            home_view,           name="home"),
    path("portfolio/",       user_dashboard_view, name="user_dashboard"),
    path("dashboard/admin/", admin_dashboard_view, name="admin_dashboard"),

    # ── User management ───────────────────────────────────────────────────────
    path("dashboard/admin/users/",                      admin_users_list,          name="admin_users_list"),
    path("dashboard/admin/users/<int:user_id>/",        admin_user_detail,         name="admin_user_detail"),
    path("dashboard/admin/users/<int:user_id>/toggle/", admin_toggle_user_active,  name="admin_toggle_user_active"),
    path("dashboard/admin/users/<int:user_id>/delete/", admin_delete_user,         name="admin_delete_user"),
]