# users/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import RegisterForm, LoginForm, VerifyOTPForm
from .models import EmailVerification, CustomUser
from datetime import timedelta


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Generate OTP
            otp = EmailVerification.generate_otp()
            verification = EmailVerification.objects.create(
                user=user,
                otp=otp,
                expires_at=timezone.now() + timedelta(minutes=10),
            )

            # Send OTP to console (instead of email)
            print(f"[DEBUG] OTP for {user.email} is {otp}")

            messages.info(request, "Account created! Please check your email for OTP (printed in console).")
            return redirect("verify_otp")
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})


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
                return redirect("home")  # Change to your homepage
            else:
                messages.error(request, "Invalid credentials")
    else:
        form = LoginForm()
    return render(request, "users/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect( "login")
