from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from billing.models import BillingAccount, LedgerEntry
from billing.units import credits_to_micro

SIGNUP_NOTE = 'Sign-up credits'


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid='billing_create_personal_account')
def create_personal_account(sender, instance, created, raw=False, **kwargs):
    """Every new user gets a personal account and the sign-up grant (study NOTEs Q12, Q17).

    Runs for the sign-up page, createsuperuser, and the admin. Not for fixtures (raw).
    """
    if not created or raw:
        return
    with transaction.atomic():
        account = BillingAccount.objects.create(kind=BillingAccount.Kind.PERSONAL, owner=instance)
        LedgerEntry.objects.create(
            account=account,
            amount_micro=credits_to_micro(settings.BILLING_SIGNUP_GRANT_CREDITS),
            kind=LedgerEntry.Kind.SIGNUP_GRANT,
            note=SIGNUP_NOTE,
        )
