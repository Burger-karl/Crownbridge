import logging
import uuid
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from types import SimpleNamespace

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.urls import reverse

from .models import InvestmentPlan, InvestmentIntent, UserInvestment
from payment.models import PlatformWallet, DepositAddress, UserBalance, Deposit
from payment.utils import get_user_available_balance
from payment.constants import RECEIVER_ADDRESSES

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_receiver_address(chain):
    """
    Return platform receiving address for a chain.
    Prefers PlatformWallet.address (DB); falls back to RECEIVER_ADDRESSES constant.
    """
    try:
        pw = PlatformWallet.objects.get(chain=chain)
        if pw.address:
            return pw.address
    except PlatformWallet.DoesNotExist:
        pass
    return RECEIVER_ADDRESSES.get(chain, "")


def _build_user_wallets(profile):
    """Return list of (field_name, address, label) for non-empty profile wallets."""
    fields = [
        ("bitcoin_id",    "Bitcoin (BTC)"),
        ("ethereum_id",   "Ethereum (ETH)"),
        ("tron_id",       "Tron (TRX)"),
        ("usdt_trc20_id", "USDT (TRC20)"),
        ("bep20_id",      "BEP20"),
    ]
    return [
        (field, getattr(profile, field), label)
        for field, label in fields
        if getattr(profile, field)
    ]


# ── public plan list ──────────────────────────────────────────────────────────

def investment_plans_list(request):
    plans = InvestmentPlan.objects.all().order_by("min_deposit")
    return render(request, "investment/investment_plans.html", {"plans": plans})


def invest_now_redirect(request, plan_id):
    plan = get_object_or_404(InvestmentPlan, pk=plan_id)
    if not request.user.is_authenticated:
        login_url = f"{reverse('login')}?next={reverse('investment:invest_page', args=[plan.id])}"
        return redirect(login_url)
    return redirect("investment:invest_page", plan.id)


# ── invest page (balance or deposit) ─────────────────────────────────────────

@login_required
def invest_page(request, plan_id):
    plan         = get_object_or_404(InvestmentPlan, pk=plan_id)
    user_balance = get_user_available_balance(request.user)

    pending_external_total = (
        Deposit.objects.filter(user=request.user, status="pending")
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    pw_qs = PlatformWallet.objects.all()
    if pw_qs.exists():
        chains = [SimpleNamespace(chain=pw.chain, display=pw.get_chain_display()) for pw in pw_qs]
    else:
        fallback = [
            ("ethereum", "Ethereum (ERC20)"),
            ("bsc",      "Binance Smart Chain (BEP20)"),
            ("tron",     "Tron (TRC20)"),
            ("bitcoin",  "Bitcoin (BTC)"),
            ("solana",   "Solana (SOL)"),
            ("polygon",  "Polygon (MATIC)"),
        ]
        chains = [SimpleNamespace(chain=c[0], display=c[1]) for c in fallback]

    if request.method == "POST":
        amount = request.POST.get("amount")
        chain  = request.POST.get("chain")
        action = request.POST.get("action", "deposit")

        try:
            amount_dec = Decimal(amount)
            if amount_dec <= Decimal("0"):
                raise InvalidOperation
        except Exception:
            messages.error(request, "Invalid amount.")
            return redirect("investment:invest_page", plan_id)

        if amount_dec < plan.min_deposit or (plan.max_deposit and amount_dec > plan.max_deposit):
            messages.error(
                request,
                f"Amount must be between ${plan.min_deposit} and ${plan.max_deposit or 'Unlimited'}.",
            )
            return redirect("investment:invest_page", plan_id)

        # ── Invest from internal balance ──────────────────────────────────────
        if action == "wallet":
            current_balance = get_user_available_balance(request.user)
            if current_balance < amount_dec:
                messages.error(request, "Insufficient available balance to invest.")
                return redirect("investment:invest_page", plan_id)

            with transaction.atomic():
                locked = UserBalance.objects.select_for_update().get(user=request.user)
                locked.debit(amount_dec, note=f"Investment into {plan.name}")

                now = timezone.now()
                UserInvestment.objects.create(
                    user=request.user,
                    plan=plan,
                    amount_invested=amount_dec,
                    profit_earned=Decimal("0"),
                    start_time=now,
                    end_time=now + timedelta(hours=plan.duration_hours),
                    is_active=True,
                    auto_payout_done=False,
                )

            messages.success(request, f"Investment of ${amount_dec:.2f} created from your balance.")
            return redirect("user_dashboard")

        else:
            messages.info(request, "To deposit from an external wallet, use 'Deposit to Invest'.")
            return redirect("investment:deposit_invest", plan_id=plan.id)

    return render(request, "investment/invest_page.html", {
        "plan":                  plan,
        "chains":                chains,
        "user_balance":          user_balance,
        "pending_external_total": pending_external_total,
    })


# ── deposit to invest ─────────────────────────────────────────────────────────

@login_required
def deposit_invest_view(request, plan_id):
    """
    Two-phase view:
      GET  → show the form (chain selector + user wallet dropdown)
      POST → create Deposit + InvestmentIntent, then re-render with the
             receiver address for the selected chain so the user knows
             where to send funds.
    """
    plan    = get_object_or_404(InvestmentPlan, pk=plan_id)
    profile = request.user.profile

    platform_wallets = PlatformWallet.objects.all()
    chain_choices    = [(pw.chain, pw.get_chain_display()) for pw in platform_wallets]
    user_wallets     = _build_user_wallets(profile)

    # Base context for both GET and POST
    base_ctx = {
        "plan":          plan,
        "chain_choices": chain_choices,
        "user_wallets":  user_wallets,
        "intent_created": False,
        "receiver_address": None,
        "selected_chain":   None,
        "deposit":          None,
    }

    if request.method == "POST":
        raw_amount   = request.POST.get("amount", "0")
        chain        = request.POST.get("chain", "")
        wallet_field = request.POST.get("user_wallet_field", "")

        try:
            amount = Decimal(raw_amount)
        except Exception:
            messages.error(request, "Invalid amount.")
            return render(request, "investment/deposit_invest.html", base_ctx)

        if amount < plan.min_deposit or (plan.max_deposit and amount > plan.max_deposit):
            messages.error(request, f"Amount must be between ${plan.min_deposit} and ${plan.max_deposit or 'Unlimited'}.")
            return render(request, "investment/deposit_invest.html", base_ctx)

        platform_wallet = get_object_or_404(PlatformWallet, chain=chain)
        from_address    = getattr(profile, wallet_field, None) if wallet_field else None

        if not from_address:
            messages.error(request, "Invalid wallet selected. Please choose a valid wallet from your profile.")
            return render(request, "investment/deposit_invest.html", base_ctx)

        # Create intent + deposit
        intent = InvestmentIntent.objects.create(
            user=request.user,
            plan=plan,
            amount=amount,
            chain=chain,
        )

        deposit = Deposit.objects.create(
            user=request.user,
            platform_wallet=platform_wallet,
            from_address=from_address,
            amount=amount,
            tx_hash=f"intent_{uuid.uuid4().hex}",
            status="pending",
            credited=False,
            admin_approved=False,     # ← requires admin approval before crediting
            investment_intent=intent,
        )

        # Get the correct receiver address for the selected chain
        receiver_address = _get_receiver_address(chain)

        messages.success(
            request,
            f"Deposit intent created. Send ${amount:.2f} via {chain.upper()} to the address below."
        )

        return render(request, "investment/deposit_invest.html", {
            **base_ctx,
            "intent_created":   True,
            "deposit":          deposit,
            "selected_chain":   chain,
            "receiver_address": receiver_address,
            "submitted_amount": amount,
            "from_address":     from_address,
        })

    # GET
    return render(request, "investment/deposit_invest.html", base_ctx)


# ── promo plan ────────────────────────────────────────────────────────────────

def promo_plan_view(request):
    plan = InvestmentPlan.objects.filter(name__iexact="Promo").first()
    return render(request, "investment/promo_plan.html", {"plan": plan})