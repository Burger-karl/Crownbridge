import logging
from decimal import Decimal
from types import SimpleNamespace

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

from .models import InvestmentPlan, InvestmentIntent, UserInvestment
from payment.models import PlatformWallet, DepositAddress, Deposit, UserBalance

logger = logging.getLogger(__name__)

# Fixed receiver wallet address for testing (per your request)
TEST_RECEIVER_WALLET = "TBVcbu56fAxhmw8akY8wjsGyad-EL4Stv66"

def investment_plans_list(request):
    """
    Public page that shows all available investment plans.
    """
    plans = InvestmentPlan.objects.all().order_by('min_deposit')
    return render(request, "investment/investment_plans.html", {"plans": plans})


def invest_now_redirect(request, plan_id):
    """
    If not authenticated send to login with next=invest_page, otherwise to invest_page.
    """
    plan = get_object_or_404(InvestmentPlan, pk=plan_id)
    if not request.user.is_authenticated:
        login_url = f"{reverse('login')}?next={reverse('investment:invest_page', args=[plan.id])}"
        return redirect(login_url)
    return redirect('investment:invest_page', plan.id)


from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from datetime import timedelta
import logging
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum

from .models import InvestmentPlan, InvestmentIntent, UserInvestment
from payment.models import PlatformWallet, DepositAddress, UserBalance, Deposit
from payment.utils import get_user_available_balance
from payment.constants import RECEIVER_ADDRESSES


logger = logging.getLogger(__name__)

# Fixed receiver wallet address for testing (per your request)
TEST_RECEIVER_WALLET = "TBVcbu56fAxhmw8akY8wjsGyad-EL4Stv66"


@login_required
def invest_page(request, plan_id):
    """
    Invest page (two flows: wallet vs deposit). Also separate internal available balance
    from pending external deposits so the user sees both.
    """
    plan = get_object_or_404(InvestmentPlan, pk=plan_id)

    # unified internal available balance (what user can spend immediately)
    user_balance = get_user_available_balance(request.user)

    # Sum of pending external deposits (deposits user made from external wallets but not credited)
    pending_external_total = Deposit.objects.filter(user=request.user, status="pending").aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")

    # Build chain options: prefer PlatformWallet objects; fallback to defaults
    pw_qs = PlatformWallet.objects.all()
    if pw_qs.exists():
        chains = [SimpleNamespace(chain=pw.chain, display=pw.get_chain_display()) for pw in pw_qs]
    else:
        fallback = [
            ("ethereum", "Ethereum (ERC20)"),
            ("bsc", "Binance Smart Chain (BEP20)"),
            ("tron", "Tron (TRC20)"),
            ("bitcoin", "Bitcoin (BTC)"),
            ("solana", "Solana (SOL)"),
            ("polygon", "Polygon (MATIC)"),
        ]
        chains = [SimpleNamespace(chain=c[0], display=c[1]) for c in fallback]

    # POST handling is only for wallet-invest flow here (deposit via external wallet is moved to deposit_invest_view)
    if request.method == "POST":
        amount = request.POST.get("amount")
        chain = request.POST.get("chain")
        action = request.POST.get("action", "deposit")  # default to deposit if missing

        # validate amount -> Decimal
        try:
            amount_dec = Decimal(amount)
            if amount_dec <= Decimal("0"):
                raise InvalidOperation("Non-positive amount")
        except Exception:
            messages.error(request, "Invalid amount.")
            return redirect("investment:invest_page", plan_id)

        # validate amount within plan bounds
        if amount_dec < plan.min_deposit or (plan.max_deposit and amount_dec > plan.max_deposit):
            messages.error(
                request,
                f"Amount must be between ${plan.min_deposit} and ${plan.max_deposit or 'Unlimited'}.",
            )
            return redirect("investment:invest_page", plan_id)

        # Wallet flow: Invest directly using internal balance
        if action == "wallet":
            # use accurate balance checker (which already deducts transfers etc)
            current_balance = get_user_available_balance(request.user)
            if current_balance < amount_dec:
                messages.error(request, "Insufficient available balance to invest.")
                return redirect("investment:invest_page", plan_id)

            # Proceed with DB lock + deduction from UserBalance table
            with transaction.atomic():
                locked_balance = UserBalance.objects.select_for_update().get(user=request.user)
                locked_balance.debit(
                    amount_dec,
                    note=f"Investment into {plan.name}",
                    reference=None,
                )

                now = timezone.now()
                end_time = now + timedelta(hours=plan.duration_hours)

                UserInvestment.objects.create(
                    user=request.user,
                    plan=plan,
                    amount_invested=amount_dec,
                    profit_earned=Decimal("0"),
                    start_time=now,
                    end_time=end_time,
                    is_active=True,
                    auto_payout_done=False,
                )

            messages.success(request, f"Investment of ${amount_dec:.2f} created from your balance.")
            return redirect("dashboard:user_dashboard")

        # Defensive: deposit action here should not be used any more (we route deposit to deposit_invest_view)
        else:
            messages.info(request, "To deposit from an external wallet, use the 'Deposit to Invest' link.")
            return redirect("investment:deposit_invest", plan_id=plan.id)

    # GET
    return render(
        request,
        "investment/invest_page.html",
        {
            "plan": plan,
            "chains": chains,
            "user_balance": user_balance,
            "pending_external_total": pending_external_total,
        },
    )

@login_required
def deposit_invest_view(request, plan_id):
    plan = get_object_or_404(InvestmentPlan, pk=plan_id)
    profile = request.user.profile

    platform_wallets = PlatformWallet.objects.all()
    chain_choices = [(pw.chain, pw.get_chain_display()) for pw in platform_wallets]

    user_wallets = []
    wallet_fields = [
        ("bitcoin_id", "Bitcoin"),
        ("ethereum_id", "Ethereum"),
        ("tron_id", "Tron"),
        ("usdt_trc20_id", "USDT (TRC20)"),
        ("bep20_id", "BEP20"),
    ]

    for field, label in wallet_fields:
        val = getattr(profile, field)
        if val:
            user_wallets.append((field, val, label))

    context = {
        "plan": plan,
        "chain_choices": chain_choices,
        "user_wallets": user_wallets,
        "intent_created": False,
    }

    if request.method == "POST":
        amount = Decimal(request.POST.get("amount"))
        chain = request.POST.get("chain")
        wallet_field = request.POST.get("user_wallet_field")

        if amount < plan.min_deposit or (plan.max_deposit and amount > plan.max_deposit):
            messages.error(request, "Amount outside plan limits.")
            return redirect("investment:deposit_invest", plan_id)

        platform_wallet = get_object_or_404(PlatformWallet, chain=chain)
        from_address = getattr(profile, wallet_field, None)

        if not from_address:
            messages.error(request, "Invalid wallet selected.")
            return redirect("investment:deposit_invest", plan_id)

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
            investment_intent=intent,
        )

        context = {
            "plan": plan,
            "chain_choices": chain_choices,
            "user_wallets": user_wallets,
            "receiver_addresses": RECEIVER_ADDRESSES,  # ✅
            "intent_created": False,
        }


        messages.success(request, "Deposit intent created. Send funds to the address below.")
        return render(request, "investment/deposit_invest.html", context)

    return render(request, "investment/deposit_invest.html", context)

    

def promo_plan_view(request):
    """
    Display the Promo plan (production-ready).
    """
    plan = InvestmentPlan.objects.filter(name__iexact="Promo").first()
    return render(request, "investment/promo_plan.html", {"plan": plan})
