from django.urls import path
from . import views

app_name = 'investment'

urlpatterns = [
    path('invest/<int:plan_id>/redirect/', views.invest_now_redirect, name='invest_redirect'),
    path('invest/<int:plan_id>/', views.invest_page, name='invest_page'),
    path('plans/', views.investment_plans_list, name='investment_plans'),

    # deposit instructions keyed by InvestmentIntent id (UUID)
    path('deposit/<uuid:intent_id>/instructions/', views.deposit_instructions_view, name='deposit_instructions'),
]
