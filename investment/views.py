import logging
from decimal import Decimal
from types import SimpleNamespace

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

from .models import InvestmentPlan, InvestmentIntent, UserInvestment
from payment.models import PlatformWallet, DepositAddress, Deposit

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


@login_required
def invest_page(request, plan_id):
    """
    Page where the user selects amount and chain. On POST creates an InvestmentIntent
    and redirects to deposit instructions page.
    """
    plan = get_object_or_404(InvestmentPlan, pk=plan_id)

    # Build chain options: prefer PlatformWallet objects; fallback to defaults
    pw_qs = PlatformWallet.objects.all()
    if pw_qs.exists():
        chains = [SimpleNamespace(chain=pw.chain, display=pw.get_chain_display()) for pw in pw_qs]
    else:
        # fallback list (expand as needed)
        fallback = [
            ("ethereum", "Ethereum (ERC20)"),
            ("bsc", "Binance Smart Chain (BEP20)"),
            ("tron", "Tron (TRC20)"),
            ("bitcoin", "Bitcoin (BTC)"),
            ("solana", "Solana (SOL)"),
            ("polygon", "Polygon (MATIC)"),
        ]
        chains = [SimpleNamespace(chain=c[0], display=c[1]) for c in fallback]

    if request.method == "POST":
        amount = request.POST.get("amount")
        chain = request.POST.get("chain")  # 'ethereum' or 'bsc' etc
        try:
            amount_dec = Decimal(amount)
        except Exception:
            messages.error(request, "Invalid amount.")
            return redirect('investment:invest_page', plan_id)

        # validate amount within plan bounds
        if amount_dec < plan.min_deposit or (plan.max_deposit and amount_dec > plan.max_deposit):
            messages.error(request, f"Amount must be between ${plan.min_deposit} and ${plan.max_deposit or 'Unlimited'}.")
            return redirect('investment:invest_page', plan_id)

        # Create a pending investment intent (we'll match it to a deposit later)
        intent = InvestmentIntent.objects.create(
            user=request.user,
            plan=plan,
            amount=amount_dec,
            chain=chain,
            completed=False
        )

        # create (or ensure) a DepositAddress row for bookkeeping (we won't rely on it for the fixed test address)
        platform_wallet = PlatformWallet.objects.filter(chain=chain).first()
        if platform_wallet:
            da, _ = DepositAddress.objects.get_or_create(user=request.user, platform_wallet=platform_wallet)
            if not da.address:
                da.generate_address()
        # Redirect to a dedicated instructions page that shows the intent
        return redirect('investment:deposit_instructions', intent_id=intent.id)

    # GET
    return render(request, "investment/invest_page.html", {"plan": plan, "chains": chains})
    

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
