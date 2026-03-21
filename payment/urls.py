from django.urls import path
from . import views

app_name = "payment"

urlpatterns = [
    # ── Withdrawal ────────────────────────────────────────────────────────────
    path("withdraw/",                                     views.withdraw_page,            name="withdraw"),
    path("withdraw/history/",                             views.withdrawal_history,       name="withdrawals"),

    # Staff — withdrawal
    path("admin/withdrawals/pending/",                    views.pending_withdrawals,      name="admin_pending_withdrawals"),
    path("admin/withdrawals/<uuid:wid>/approve/",         views.approve_withdrawal,       name="approve_withdrawal"),
    path("admin/withdrawals/<uuid:wid>/decline/",         views.decline_withdrawal,       name="decline_withdrawal"),
    path("withdraw/<uuid:wid>/pay/",                      views.admin_withdrawal_payment, name="withdrawal_payment_page"),

    # ── Deposit ───────────────────────────────────────────────────────────────
    path("deposit/",                                      views.deposit_page,             name="deposit"),
    path("deposit/<uuid:deposit_id>/instructions/",       views.deposit_instructions,     name="deposit_instructions"),
    path("deposit/history/",                              views.deposit_history,          name="deposit_history"),

    # Staff — deposit approval  ← NEW
    path("admin/deposits/pending/",                       views.admin_pending_deposits,   name="admin_pending_deposits"),
    path("admin/deposits/<uuid:deposit_id>/approve/",     views.admin_approve_deposit,    name="admin_approve_deposit"),
    path("admin/deposits/<uuid:deposit_id>/reject/",      views.admin_reject_deposit,     name="admin_reject_deposit"),

    # ── Transfers ─────────────────────────────────────────────────────────────
    path("transfer/history/",                             views.transfer_history,         name="transfer_history"),
    path("p2ptransfer/",                                  views.p2p_transfer_view,        name="p2ptransfer"),
    path("transactions/",                                 views.transaction_history_view, name="transaction_history"),

    # ── Blockchain confirmation endpoints ─────────────────────────────────────
    path("tron_deposit/",                                 views.confirm_tron_deposit,     name="confirm_tron_deposit"),
    path("eth_deposit/",                                  views.confirm_eth_deposit,      name="confirm_eth_deposit"),
]