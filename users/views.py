
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from .forms import RegisterForm, LoginForm, ProfileEditForm
from .models import CustomUser

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def register_view(request):
    # Redirect already-authenticated users
    if request.user.is_authenticated:
        return redirect("user_dashboard")

    ref_code = request.GET.get("ref") or request.POST.get("referral_code")
    ref_user = None

    if ref_code:
        try:
            ref_user = CustomUser.objects.get(referral_code=ref_code)
        except CustomUser.DoesNotExist:
            pass  # Invalid ref code — silently ignore

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            if ref_user and ref_user.pk != user.pk:
                user.referred_by = ref_user

            user.save()

            # Profile wallets are saved inside RegisterForm.save()
            logger.info("New user registered: %s", user.email)
            messages.success(request, "Registration successful. Please log in.")
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "users/register.html", {
        "form": form,
        "referral_code": ref_code,
        "ref_user": ref_user,
    })


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("user_dashboard")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(request, email=email, password=password)

            if user:
                if not user.is_active:
                    messages.error(request, "Your account has been disabled. Contact support.")
                    return render(request, "users/login.html", {"form": form})

                login(request, user)
                logger.info("User logged in: %s", user.email)
                messages.success(request, f"Welcome back, {user.full_name or user.email}!")

                if user.is_staff or user.is_superuser:
                    return redirect("admin_dashboard")

                # Honor "next" redirect from @login_required
                next_url = request.GET.get("next") or request.POST.get("next")
                return redirect(next_url if next_url and next_url.startswith("/") else "user_dashboard")

            messages.error(request, "Invalid email or password.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = LoginForm()

    return render(request, "users/login.html", {"form": form})


# @login_required
# def logout_view(request):
#     # POST-only logout to prevent CSRF logout attacks
#     if request.method == "POST":
#         logger.info("User logged out: %s", request.user.email)
#         logout(request)
#         messages.success(request, "You have been logged out.")
#     return redirect("login")

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect( "login")


@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, "users/profile.html", {"profile": profile})


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile_view(request):
    profile = request.user.profile

    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            logger.info("Profile updated for user: %s", request.user.email)
            messages.success(request, "Profile updated successfully!")
            return redirect("profile")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ProfileEditForm(instance=profile)

    return render(request, "users/edit_profile.html", {
        "form": form,
        "profile": profile,
        "user": request.user,
    })