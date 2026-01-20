from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from .forms import RegisterForm, LoginForm, ProfileEditForm
from .models import CustomUser
from datetime import timedelta

def register_view(request):
    ref_code = request.GET.get("ref") or request.POST.get("referral_code")
    ref_user = None

    if ref_code:
        try:
            ref_user = CustomUser.objects.get(referral_code=ref_code)
        except CustomUser.DoesNotExist:
            pass

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            if ref_user and ref_user != user:
                user.referred_by = ref_user

            user.save()

            # Save profile crypto wallets
            profile = user.profile
            profile.email = user.email
            profile.bitcoin_id = form.cleaned_data.get("bitcoin_id")
            profile.ethereum_id = form.cleaned_data.get("ethereum_id")
            profile.usdt_trc20_id = form.cleaned_data.get("usdt_trc20_id")
            profile.tron_id = form.cleaned_data.get("tron_id")
            profile.bep20_id = form.cleaned_data.get("bep20_id")
            profile.save()

            messages.success(
                request,
                "Registration successful. Please log in."
            )

            return redirect("login")  # ✅ DIRECT TO LOGIN

    else:
        form = RegisterForm()

    return render(request, "users/register.html", {
        "form": form,
        "referral_code": ref_code,
        "ref_user": ref_user
    })


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(request, email=email, password=password)

            if user:
                login(request, user)
                messages.success(request, f"Welcome back {user.full_name or user.email}!")

                if user.is_staff or user.is_superuser:
                    return redirect("admin_dashboard")

                return redirect("user_dashboard")

            messages.error(request, "Invalid credentials")

    else:
        form = LoginForm()

    return render(request, "users/login.html", {"form": form})


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
def edit_profile_view(request):
    profile = request.user.profile

    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("profile")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ProfileEditForm(instance=profile)

    return render(request, "users/edit_profile.html", {"form": form, "profile": profile, "user": request.user})