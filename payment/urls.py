# payment/urls.py
from django.urls import path
from . import views

app_name = "payment"

urlpatterns = [
    path("withdraw/", views.withdraw_page, name="withdraw"),
    path("withdraw/history/", views.withdrawal_history, name="withdrawals"),
    # Staff endpoints
    path("admin/withdrawals/pending/", views.pending_withdrawals, name="admin_pending_withdrawals"),
    path("admin/withdrawals/<uuid:wid>/approve/", views.approve_withdrawal, name="approve_withdrawal"),
    path("admin/withdrawals/<uuid:wid>/decline/", views.decline_withdrawal, name="decline_withdrawal"),
    # Simulated "payment" page for approved withdrawals
    path("withdraw/<uuid:wid>/pay/", views.withdrawal_payment_page, name="withdrawal_payment_page"),
]
