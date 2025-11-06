from django.urls import path
from .views import verify_kyc, kyc_list_view, approve_kyc_view, reject_kyc_view

app_name = "kyc"

urlpatterns = [
    path("verify/", verify_kyc, name="verify"),
    
    # Admin views
    path("admin/list/", kyc_list_view, name="admin_kyc_list"),
    path("admin/approve/<int:pk>/", approve_kyc_view, name="approve_kyc"),
    path("admin/reject/<int:pk>/", reject_kyc_view, name="reject_kyc"),
]
