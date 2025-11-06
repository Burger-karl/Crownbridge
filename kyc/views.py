from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import KYCForm

@login_required
def verify_kyc(request):
    kyc = getattr(request.user, "kyc", None)

    if request.method == "POST":
        form = KYCForm(request.POST, request.FILES, instance=kyc)
        if form.is_valid():
            kyc = form.save(commit=False)
            kyc.user = request.user
            kyc.save()
            messages.success(request, "KYC submitted successfully! Await verification.")
            return redirect("dashboard:user_dashboard")
    else:
        form = KYCForm(instance=kyc)

    return render(request, "kyc/verify.html", {"form": form})


# kyc/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from .models import KYCVerification


def admin_required(user):
    return user.is_staff or user.is_superuser


@user_passes_test(admin_required)
def kyc_list_view(request):
    """
    Admin-only: View all KYC submissions (pending and verified)
    """
    kycs = KYCVerification.objects.select_related("user").order_by("-submitted_at")
    return render(request, "kyc/admin_kyc_list.html", {"kycs": kycs})


@user_passes_test(admin_required)
def approve_kyc_view(request, pk):
    """
    Admin approves a user's KYC submission
    """
    kyc = get_object_or_404(KYCVerification, pk=pk)
    if not kyc.verified:
        kyc.verified = True
        kyc.save()
        messages.success(request, f"KYC for {kyc.user.email} has been approved successfully.")
    else:
        messages.info(request, f"KYC for {kyc.user.email} is already verified.")
    return redirect("kyc:admin_kyc_list")


@user_passes_test(admin_required)
def reject_kyc_view(request, pk):
    """
    Admin rejects (deletes) a user's KYC submission
    """
    kyc = get_object_or_404(KYCVerification, pk=pk)
    user_email = kyc.user.email
    kyc.delete()
    messages.warning(request, f"KYC submission for {user_email} has been rejected and removed.")
    return redirect("kyc:admin_kyc_list")
