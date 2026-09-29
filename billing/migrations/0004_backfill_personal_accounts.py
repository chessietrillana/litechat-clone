"""Give users made before billing existed a personal account and the sign-up grant.

Data migrations don't fire signals, so this creates the rows itself.
Users who already have a personal account are skipped, so running it again
does nothing. Undoing the migration deletes nothing.
"""
from django.conf import settings
from django.db import migrations

MICRO_PER_CREDIT = 1_000_000  # copied, not imported: migrations must not depend on app code


def backfill(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    BillingAccount = apps.get_model('billing', 'BillingAccount')
    LedgerEntry = apps.get_model('billing', 'LedgerEntry')
    grant_micro = int(settings.BILLING_SIGNUP_GRANT_CREDITS) * MICRO_PER_CREDIT
    has_account = BillingAccount.objects.filter(kind='personal').values('owner')
    for user in User.objects.exclude(pk__in=has_account):
        account = BillingAccount.objects.create(kind='personal', owner=user)
        LedgerEntry.objects.create(
            account=account, amount_micro=grant_micro, kind='signup_grant', note='Sign-up credits',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_seed_tier_prices'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
