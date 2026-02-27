# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile"
    fk_name = "user"
    fields = (
        "firstname", "lastname", "country", "phone", "email",
        "bitcoin_id", "ethereum_id", "usdt_trc20_id", "tron_id", "bep20_id",
    )


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = (
        "id", "email", "full_name", "kyc_verified",
        "is_active", "is_staff", "date_joined",
    )
    list_filter = ("is_active", "is_staff", "kyc_verified")
    search_fields = ("email", "full_name")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login", "referral_code")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        ("Referral", {"fields": ("referral_code", "referred_by", "referral_bonus_percent")}),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "kyc_verified", "groups", "user_permissions"),
        }),
        ("Dates", {"fields": ("date_joined", "last_login")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "password1", "password2"),
        }),
    )

    # Required by BaseUserAdmin (uses username by default — our model uses email)
    username_field = "email"