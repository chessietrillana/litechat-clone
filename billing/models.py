from django.conf import settings
from django.db import models
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from billing.units import format_credits, micro_to_credits


class BillingAccountQuerySet(models.QuerySet):
    def for_user(self, user):
        """Accounts the user may bill to: their personal one plus shared ones they belong to."""
        member_of = BillingAccount.members.through.objects.filter(user=user).values('billingaccount')
        return self.filter(
            Q(kind=BillingAccount.Kind.PERSONAL, owner=user)
            | Q(kind=BillingAccount.Kind.SHARED, pk__in=member_of)
        )

    def with_balance(self):
        """Add `balance` (µc). A subquery, so filters on members can't double-count entries."""
        totals = (
            LedgerEntry.objects.filter(account=OuterRef('pk'))
            .values('account')
            .annotate(total=Sum('amount_micro'))
            .values('total')
        )
        return self.annotate(balance=Coalesce(Subquery(totals), 0))


class BillingAccount(models.Model):
    class Kind(models.TextChoices):
        PERSONAL = 'personal', 'Personal'
        SHARED = 'shared', 'Shared'

    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=100, blank=True, help_text='Required for shared accounts.')
    # Cascade here, but LedgerEntry.account is PROTECT: a user whose personal
    # account has entries cannot be deleted (ProtectedError).
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name='owned_billing_accounts', help_text='Set for personal accounts only.',
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='billing_accounts',
        help_text='Users who may bill to this shared account.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BillingAccountQuerySet.as_manager()

    class Meta:
        ordering = ['kind', 'name', 'id']
        constraints = [
            models.CheckConstraint(
                condition=Q(kind='personal', owner__isnull=False) | Q(kind='shared', owner__isnull=True),
                name='billing_account_owner_matches_kind',
            ),
            models.CheckConstraint(
                condition=Q(kind='personal') | ~Q(name=''),
                name='billing_account_shared_needs_name',
            ),
            models.UniqueConstraint(
                fields=['owner'], condition=Q(kind='personal'),
                name='billing_account_one_personal_per_user',
            ),
        ]

    def __str__(self):
        if self.kind == self.Kind.PERSONAL:
            return f'{self.owner.username} (personal)'
        return self.name

    def balance_micro(self):
        return self.entries.aggregate(total=Coalesce(Sum('amount_micro'), 0))['total']


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        SIGNUP_GRANT = 'signup_grant', 'Sign-up grant'
        ADMIN_GRANT = 'admin_grant', 'Admin grant'

    account = models.ForeignKey(BillingAccount, on_delete=models.PROTECT, related_name='entries')
    amount_micro = models.BigIntegerField(help_text='Micro-credits. Positive adds credits.')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name_plural = 'ledger entries'

    def __str__(self):
        return f'{self.get_kind_display()} {format_credits(self.amount_micro)} credits to {self.account}'

    @property
    def amount_credits(self):
        return micro_to_credits(self.amount_micro)
