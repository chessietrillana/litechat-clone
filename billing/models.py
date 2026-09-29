from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from billing.units import format_credits, micro_to_credits
from catalog.models import Tier


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
        CHARGE = 'charge', 'Charge'

    account = models.ForeignKey(BillingAccount, on_delete=models.PROTECT, related_name='entries')
    amount_micro = models.BigIntegerField(help_text='Micro-credits. Positive adds credits.')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    note = models.CharField(max_length=200, blank=True)
    # Grants: the admin who gave them. Charges: the user who sent the message.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Charges only: what was billed, at which price (study NOTE Q10).
    tokens = models.PositiveIntegerField(null=True, blank=True, help_text='Charges only. Input + output tokens.')
    price_per_1k_tokens = models.DecimalField(
        'price per 1K tokens (credits)', max_digits=12, decimal_places=3, null=True, blank=True,
        help_text='Charges only. The tier price when the message was sent.',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name_plural = 'ledger entries'
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind='charge', tokens__isnull=False, price_per_1k_tokens__isnull=False,
                      amount_micro__lte=0)
                    | (~Q(kind='charge') & Q(tokens__isnull=True, price_per_1k_tokens__isnull=True))
                ),
                name='ledger_entry_charge_fields',
            ),
        ]

    def __str__(self):
        return f'{self.get_kind_display()} {format_credits(self.amount_micro)} credits to {self.account}'

    @property
    def amount_credits(self):
        return micro_to_credits(self.amount_micro)


class TierPrice(models.Model):
    """Price per 1K tokens for one tier (study NOTEs Q5, Q6, Q9).

    Input, output, and cached tokens all cost the same.
    """
    tier = models.PositiveSmallIntegerField(choices=Tier.choices, unique=True)
    price_per_1k_tokens = models.DecimalField(
        'price per 1K tokens (credits)', max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0'))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tier']
        constraints = [
            models.CheckConstraint(
                condition=Q(price_per_1k_tokens__gte=0), name='tier_price_not_negative',
            ),
        ]

    def __str__(self):
        price = Decimal(self.price_per_1k_tokens).normalize()
        return f'{self.get_tier_display()}: {price:f} credits per 1K tokens'

    @property
    def micro_per_token(self):
        """Exact µc per token: credits per 1K x 1,000,000 µc / 1,000 tokens."""
        return int(Decimal(self.price_per_1k_tokens).scaleb(3))

    def cost_micro(self, tokens):
        """Exact cost of `tokens` in µc."""
        return tokens * self.micro_per_token
