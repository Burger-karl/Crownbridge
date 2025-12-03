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
            return redirect("investment:user_investments")

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
    """
    New: Deposit-from-external-wallet feature for investing.
    - GET: show a form: amount, chain, user's saved wallet IDs dropdown (only those with data),
           show platform receiver wallet/address.
    - POST: validate + create InvestmentIntent and a Deposit row with status='pending' so you can confirm it later.
            After POST, render the same page but show the receiver address and "pending" instructions (no redirect).
    """
    plan = get_object_or_404(InvestmentPlan, pk=plan_id)

    # Available platform chains (prefer PlatformWallet rows)
    platform_wallets = PlatformWallet.objects.all()
    if platform_wallets.exists():
        chain_choices = [(pw.chain, pw.get_chain_display()) for pw in platform_wallets]
    else:
        chain_choices = [
            ("ethereum", "Ethereum (ERC20)"),
            ("bsc", "Binance Smart Chain (BEP20)"),
            ("tron", "Tron (TRC20)"),
            ("bitcoin", "Bitcoin (BTC)"),
            ("solana", "Solana (SOL)"),
            ("polygon", "Polygon (MATIC)"),
        ]

    # Build user's saved wallet IDs from profile (only non-empty values)
    profile = request.user.profile
    user_wallets = []  # list of (field_name, value, label)
    # fields we added earlier on Profile
    wallet_fields = [
        ("bitcoin_id", "Bitcoin"),
        ("ethereum_id", "Ethereum"),
        ("usdt_trc20_id", "USDT (TRC20)"),
        ("tron_id", "Tron"),
        ("bep20_id", "BEP20 (Binance)"),
    ]
    for field_name, label in wallet_fields:
        val = getattr(profile, field_name, None)
        if val:
            user_wallets.append((field_name, val, label))

    # default context values for GET & (after POST) render
    context = {
        "plan": plan,
        "chain_choices": chain_choices,
        "user_wallets": user_wallets,
        "platform_receiver": TEST_RECEIVER_WALLET,
        "intent_created": False,
        "intent": None,
    }

    if request.method == "POST":
        amount = request.POST.get("amount")
        chain = request.POST.get("chain")
        selected_user_wallet_field = request.POST.get("user_wallet_field")  # e.g. 'bitcoin_id'
        # Validate requested chain is allowed
        allowed_chains = [c[0] for c in chain_choices]
        if chain not in allowed_chains:
            messages.error(request, "Selected chain is not allowed.")
            return redirect("investment:deposit_invest", plan_id=plan_id)

        # Parse amount
        try:
            amount_dec = Decimal(amount)
            if amount_dec <= Decimal("0"):
                raise InvalidOperation("Non-positive amount")
        except Exception:
            messages.error(request, "Invalid amount.")
            return redirect("investment:deposit_invest", plan_id=plan_id)

        # Validate plan bounds
        if amount_dec < plan.min_deposit or (plan.max_deposit and amount_dec > plan.max_deposit):
            messages.error(
                request,
                f"Amount must be between ${plan.min_deposit} and ${plan.max_deposit or 'Unlimited'}.",
            )
            return redirect("investment:deposit_invest", plan_id=plan_id)

        # Ensure selected_user_wallet_field belongs to the user and has value
        selected_wallet_value = None
        if selected_user_wallet_field:
            selected_wallet_value = getattr(profile, selected_user_wallet_field, None)
            if not selected_wallet_value:
                messages.error(request, "Selected wallet ID is not valid.")
                return redirect("investment:deposit_invest", plan_id=plan_id)

        # find platform wallet row for the selected chain (if exists)
        platform_wallet = PlatformWallet.objects.filter(chain=chain).first()

        # Create InvestmentIntent (pending) and a matching Deposit (status pending)
        try:
            intent = InvestmentIntent.objects.create(
                user=request.user,
                plan=plan,
                amount=amount_dec,
                chain=chain,
                completed=False,
            )

            # create deposit row (status pending) for tracking — tx_hash left blank for the user to supply later
            deposit = Deposit.objects.create(
                user=request.user,
                platform_wallet=platform_wallet,
                deposit_address=None,
                tx_hash=str(uuid.uuid4()),  # placeholder; your confirm command can update tx_hash
                from_address=selected_wallet_value or "",
                token_contract=None,
                amount=amount_dec,
                confirmations=0,
                status="pending",
                credited=False,
            )

            # return the same page but render receiver and intent details so user can proceed to send funds
            context.update({
                "intent_created": True,
                "intent": intent,
                "deposit": deposit,
                "selected_wallet_value": selected_wallet_value,
                "platform_receiver": TEST_RECEIVER_WALLET,
            })

            messages.success(request, "Investment intent created. Please send the funds to the receiver address below.")
            # render the page showing instructions (no redirect)
            return render(request, "investment/deposit_invest.html", context)

        except Exception as e:
            logger.exception("Failed to create deposit intent for user %s: %s", request.user, e)
            messages.error(request, "Could not create deposit intent. Please try again or contact support.")
            return redirect("investment:deposit_invest", plan_id=plan_id)

    # GET -> show form
    return render(request, "investment/deposit_invest.html", context)
    

@login_required
def deposit_instructions_view(request, intent_id):
    """
    Show deposit instructions for a given InvestmentIntent.
    We use a fixed receiver wallet for testing (TEST_RECEIVER_WALLET).
    """
    intent = get_object_or_404(InvestmentIntent, pk=intent_id, user=request.user)

    # For testing we use a constant receiver wallet address you supplied
    receiver_wallet = TEST_RECEIVER_WALLET

    # Create or update a Deposit record representing the pending intent (pseudo tx_hash)
    pseudo_tx = f"intent_{intent.id}"
    deposit, created = Deposit.objects.get_or_create(
        tx_hash=pseudo_tx,
        defaults={
            "user": request.user,
            "platform_wallet": PlatformWallet.objects.filter(chain=intent.chain).first(),
            "deposit_address": None,
            "amount": intent.amount,
            "status": "pending",
            "credited": False,
        },
    )

    context = {
        "plan": intent.plan,
        "amount": intent.amount,
        "chain": intent.chain,
        "deposit_address": receiver_wallet,
        "intent": intent,
        "deposit": deposit,
    }
    return render(request, "investment/deposit_instructions.html", context)

def promo_plan_view(request):
    """
    Display the Promo plan (production-ready).
    """
    plan = InvestmentPlan.objects.filter(name__iexact="Promo").first()
    return render(request, "investment/promo_plan.html", {"plan": plan})
