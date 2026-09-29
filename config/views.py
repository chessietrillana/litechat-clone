from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from billing.models import BillingAccount


@login_required
def home(request):
    accounts = BillingAccount.objects.for_user(request.user).with_balance()
    return render(request, 'home.html', {'billing_accounts': accounts})
