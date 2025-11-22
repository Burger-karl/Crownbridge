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
    path("withdraw/<uuid:wid>/pay/", views.withdrawal_payment_page, name="withdrawal_payment_page"),

    # Deposit flow
    path('deposit/', views.deposit_page, name='deposit'),
    path('deposit/<uuid:deposit_id>/instructions/', views.deposit_instructions, name='deposit_instructions'),
    path('deposit/history/', views.deposit_history, name='deposit_history'),

    # Transfers
    path('transfer/', views.transfer_page, name='transfer'),
    path('transfer/history/', views.transfer_history, name='transfer_history'),
    path("p2ptransfer/", views.p2p_transfer_view, name="p2ptransfer")

]
