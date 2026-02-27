
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import KYCVerification


@admin.register(KYCVerification)
class KYCVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "user_email",
        "full_name",
        "status_badge",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = ("status", "submitted_at")
    search_fields = ("user__email", "full_name")
    readonly_fields = (
        "user",
        "submitted_at",
        "updated_at",
        "id_document_preview",
        "selfie_preview",
    )
    actions = ["approve_selected", "reject_selected"]

    fieldsets = (
        ("Submission", {
            "fields": ("user", "full_name", "submitted_at", "updated_at"),
        }),
        ("Documents", {
            "fields": ("id_document", "id_document_preview", "selfie", "selfie_preview"),
        }),
        ("Review", {
            "fields": ("status", "verified", "reviewed_by", "reviewed_at", "rejection_reason", "admin_notes"),
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User"

    def status_badge(self, obj):
        colors = {
            "pending": "orange",
            "approved": "green",
            "rejected": "red",
        }
        color = colors.get(obj.status, "grey")
        return format_html(
            '<span style="color:white;background:{};padding:2px 8px;border-radius:4px;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def id_document_preview(self, obj):
        if obj.id_document:
            return format_html('<a href="{}" target="_blank">View ID Document</a>', obj.id_document.url)
        return "No document"
    id_document_preview.short_description = "ID Document"

    def selfie_preview(self, obj):
        if obj.selfie:
            return format_html(
                '<a href="{url}" target="_blank"><img src="{url}" height="150" style="border-radius:8px;"/></a>',
                url=obj.selfie.url,
            )
        return "No selfie"
    selfie_preview.short_description = "Selfie"

    def approve_selected(self, request, queryset):
        count = 0
        for kyc in queryset.exclude(status=KYCVerification.STATUS_APPROVED):
            kyc.status = KYCVerification.STATUS_APPROVED
            kyc.verified = True
            kyc.reviewed_by = request.user
            kyc.reviewed_at = timezone.now()
            kyc.save()
            kyc.user.kyc_verified = True
            kyc.user.save(update_fields=["kyc_verified"])
            count += 1
        self.message_user(request, f"{count} KYC submission(s) approved.")
    approve_selected.short_description = "Approve selected KYC submissions"

    def reject_selected(self, request, queryset):
        count = 0
        for kyc in queryset.exclude(status=KYCVerification.STATUS_REJECTED):
            kyc.status = KYCVerification.STATUS_REJECTED
            kyc.verified = False
            kyc.reviewed_by = request.user
            kyc.reviewed_at = timezone.now()
            kyc.rejection_reason = "Rejected via bulk action – please resubmit."
            kyc.save()
            kyc.user.kyc_verified = False
            kyc.user.save(update_fields=["kyc_verified"])
            count += 1
        self.message_user(request, f"{count} KYC submission(s) rejected.")
    reject_selected.short_description = "Reject selected KYC submissions"