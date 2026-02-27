# kyc/views.py
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import KYCForm, KYCRejectForm
from .models import KYCVerification

logger = logging.getLogger(__name__)

def admin_required(user):
    return user.is_staff or user.is_superuser


# User views

@login_required
def verify_kyc(request):
    """User submits (or re-submits) KYC documents."""
    kyc = getattr(request.user, "kyc", None)

    # If already approved, just show status — no need to re-submit
    if kyc and kyc.is_approved:
        messages.info(request, "Your KYC has already been verified.")
        return redirect("dashboard:user_dashboard")

    if request.method == "POST":
        form = KYCForm(request.POST, request.FILES, instance=kyc)
        if form.is_valid():
            kyc_obj = form.save(commit=False)
            kyc_obj.user = request.user
            # Reset status to pending on every (re-)submission
            kyc_obj.status = KYCVerification.STATUS_PENDING
            kyc_obj.verified = False
            kyc_obj.rejection_reason = ""
            kyc_obj.reviewed_by = None
            kyc_obj.reviewed_at = None
            kyc_obj.save()
            logger.info("KYC submitted by user %s", request.user.email)
            messages.success(request, "KYC submitted successfully! Await verification.")
            return redirect("dashboard:user_dashboard")
    else:
        form = KYCForm(instance=kyc)

    return render(request, "kyc/verify.html", {"form": form, "kyc": kyc})


# Admin views

@user_passes_test(admin_required)
def kyc_list_view(request):
    """Admin: list all KYC submissions with optional filter."""
    status_filter = request.GET.get("status", "")
    kycs = KYCVerification.objects.select_related("user", "reviewed_by").order_by("-submitted_at")

    if status_filter in (KYCVerification.STATUS_PENDING, KYCVerification.STATUS_APPROVED, KYCVerification.STATUS_REJECTED):
        kycs = kycs.filter(status=status_filter)

    counts = {
        "all": KYCVerification.objects.count(),
        "pending": KYCVerification.objects.filter(status=KYCVerification.STATUS_PENDING).count(),
        "approved": KYCVerification.objects.filter(status=KYCVerification.STATUS_APPROVED).count(),
        "rejected": KYCVerification.objects.filter(status=KYCVerification.STATUS_REJECTED).count(),
    }

    return render(request, "kyc/admin_kyc_list.html", {
        "kycs": kycs,
        "status_filter": status_filter,
        "counts": counts,
    })


@user_passes_test(admin_required)
def kyc_detail_view(request, pk):
    """Admin: view a single KYC submission in detail."""
    kyc = get_object_or_404(KYCVerification.objects.select_related("user", "reviewed_by"), pk=pk)
    reject_form = KYCRejectForm()
    return render(request, "kyc/admin_kyc_detail.html", {
        "kyc": kyc,
        "reject_form": reject_form,
    })


@require_POST
@user_passes_test(admin_required)
def approve_kyc_view(request, pk):
    """Admin approves a KYC submission."""
    kyc = get_object_or_404(KYCVerification, pk=pk)

    if kyc.is_approved:
        messages.info(request, f"KYC for {kyc.user.email} is already approved.")
        return redirect("kyc:admin_kyc_list")

    kyc.status = KYCVerification.STATUS_APPROVED
    kyc.verified = True
    kyc.reviewed_by = request.user
    kyc.reviewed_at = timezone.now()
    kyc.rejection_reason = ""
    kyc.save()

    # Also update the user model flag
    kyc.user.kyc_verified = True
    kyc.user.save(update_fields=["kyc_verified"])

    logger.info("KYC approved for %s by admin %s", kyc.user.email, request.user.email)
    messages.success(request, f"KYC for {kyc.user.email} has been approved.")
    return redirect("kyc:admin_kyc_list")


@require_POST
@user_passes_test(admin_required)
def reject_kyc_view(request, pk):
    """Admin rejects a KYC submission with a mandatory reason."""
    kyc = get_object_or_404(KYCVerification, pk=pk)
    form = KYCRejectForm(request.POST)

    if form.is_valid():
        kyc.status = KYCVerification.STATUS_REJECTED
        kyc.verified = False
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.rejection_reason = form.cleaned_data["rejection_reason"]
        kyc.admin_notes = form.cleaned_data.get("admin_notes", "")
        kyc.save()

        # Clear the user's kyc_verified flag
        kyc.user.kyc_verified = False
        kyc.user.save(update_fields=["kyc_verified"])

        logger.info("KYC rejected for %s by admin %s", kyc.user.email, request.user.email)
        messages.warning(request, f"KYC for {kyc.user.email} has been rejected.")
    else:
        messages.error(request, "Please provide a rejection reason.")

    return redirect("kyc:admin_kyc_list")