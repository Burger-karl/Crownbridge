from django.contrib import admin
from .models import UserInvestment, InvestmentIntent
# Register your models here.


@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'amount_invested', 'profit_earned', 'start_time', 'end_time', 'is_active', 'auto_payout_done')

@admin.register(InvestmentIntent)
class InvestmentIntentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'amount', 'chain', 'created_at', 'completed', 'deposit_tx')

