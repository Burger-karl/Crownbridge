# kyc/urls.py
from django.urls import path
from .views import (
    verify_kyc,
    kyc_list_view,
    kyc_detail_view,
    approve_kyc_view,
    reject_kyc_view,
)

app_name = "kyc"

urlpatterns = [
    # User
    path("verify/", verify_kyc, name="verify"),

    # Admin views
    path("admin/list/", kyc_list_view, name="admin_kyc_list"),
    path("admin/<int:pk>/", kyc_detail_view, name="admin_kyc_detail"),
    path("admin/<int:pk>/approve/", approve_kyc_view, name="approve_kyc"),
    path("admin/<int:pk>/reject/", reject_kyc_view, name="reject_kyc"),
]