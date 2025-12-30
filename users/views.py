from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from .forms import RegisterForm, LoginForm, VerifyOTPForm, ProfileEditForm
from .models import EmailVerification, CustomUser
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

            # 🔥 SAVE PROFILE WALLET IDS
            profile = user.profile
            profile.bitcoin_id = form.cleaned_data.get("bitcoin_id")
            profile.ethereum_id = form.cleaned_data.get("ethereum_id")
            profile.usdt_trc20_id = form.cleaned_data.get("usdt_trc20_id")
            profile.tron_id = form.cleaned_data.get("tron_id")
            profile.bep20_id = form.cleaned_data.get("bep20_id")
            profile.email = user.email
            profile.save()

            # OTP logic
            otp = EmailVerification.generate_otp()
            EmailVerification.objects.create(
                user=user,
                otp=otp,
                expires_at=timezone.now() + timedelta(minutes=10),
            )

            print(f"[DEBUG] OTP for {user.email} is {otp}")

            messages.info(
                request,
                "Account created! An OTP has been printed to the console. Please verify your email."
            )
            return redirect(f"{reverse('verify_otp')}?email={user.email}")
    else:
        form = RegisterForm()

    return render(request, "users/register.html", {
        "form": form,
        "referral_code": ref_code,
        "ref_user": ref_user
    })


def verify_otp_view(request):
    if request.method == "POST":
        form = VerifyOTPForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            otp = form.cleaned_data["otp"]

            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                messages.error(request, "No user found with this email.")
                return redirect("verify_otp")

            try:
                verification = EmailVerification.objects.filter(user=user, otp=otp).latest("created_at")
            except EmailVerification.DoesNotExist:
                messages.error(request, "Invalid OTP.")
                return redirect("verify_otp")

            if verification.is_expired():
                messages.error(request, "OTP expired. Please register again.")
                return redirect("register")

            # Mark user as verified
            user.is_verified = True
            user.save()
            messages.success(request, "Email verified successfully! You can now log in.")
            return redirect("login")
    else:
        form = VerifyOTPForm()
    return render(request, "users/verify_otp.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(request, email=email, password=password)

            if user is not None:
                if not user.is_verified:
                    messages.error(request, "Please verify your email before logging in.")
                    return redirect("verify_otp")

                login(request, user)
                messages.success(request, f"Welcome back {user.full_name or user.email}!")

                # 🔑 Admin redirect
                if user.is_staff or user.is_superuser:
                    return redirect("admin_dashboard")

                # 👤 Normal user redirect
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