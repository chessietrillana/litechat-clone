from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.http import require_safe

from billing.models import BillingAccount, LedgerEntry

CHARGES_PER_PAGE = 50


@login_required
@require_safe
def usage(request):
    """Read-only list of the user's accounts and their own charges (study NOTE Q28)."""
    accounts = BillingAccount.objects.for_user(request.user).with_balance().select_related('owner')
    # Only charges this user made. On a shared account, other members' charges
    # are not listed, but they still count in the balance.
    charges = (
        LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CHARGE, created_by=request.user)
        .select_related('account__owner', 'chat_message__session__llm_model')
    )
    page = Paginator(charges, CHARGES_PER_PAGE).get_page(request.GET.get('page'))
    return render(request, 'billing/usage.html', {'accounts': accounts, 'page': page})
