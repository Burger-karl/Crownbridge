from django.urls import path
from . import views

app_name = "investment"

urlpatterns = [
    path("invest/<int:plan_id>/redirect/", views.invest_now_redirect, name="invest_redirect"),
    path("invest/<int:plan_id>/", views.invest_page, name="invest_page"),
    path("plans/", views.investment_plans_list, name="investment_plans"),
    path("promo/", views.promo_plan_view, name="promo_plan"),

    # deposit instructions keyed by InvestmentIntent id (UUID)
    path("deposit/<uuid:intent_id>/instructions/", views.deposit_instructions_view, name="deposit_instructions"),

    # NEW: deposit-from-external-wallet to invest (no redirect; shows receiver info)
    path("deposit/invest/<int:plan_id>/", views.deposit_invest_view, name="deposit_invest"),
]
