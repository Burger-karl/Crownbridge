from django.contrib import admin
from .models import CustomUser

# Register your models here.


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'full_name', 'is_verified', 'is_active', 'is_staff', 'date_joined')
