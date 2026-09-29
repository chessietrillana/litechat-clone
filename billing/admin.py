from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from billing.forms import BillingAccountForm, GrantForm
from billing.models import BillingAccount, LedgerEntry, TierPrice
from billing.units import format_credits


class LedgerEntryInline(admin.TabularInline):
    """Read-only list of an account's entries. Grants are added on their own page."""
    model = LedgerEntry
    fields = ['created_at', 'kind', 'amount', 'tokens', 'price_per_1k_tokens', 'note', 'created_by']
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    @admin.display(description='Amount (credits)')
    def amount(self, entry):
        return format_credits(entry.amount_micro)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BillingAccount)
class BillingAccountAdmin(admin.ModelAdmin):
    form = BillingAccountForm
    list_display = ['__str__', 'kind', 'owner', 'member_count', 'balance']
    list_filter = ['kind']
    search_fields = ['name', 'owner__username']
    filter_horizontal = ['members']
    inlines = [LedgerEntryInline]

    def get_queryset(self, request):
        return super().get_queryset(request).with_balance().annotate(member_count=Count('members'))

    def get_fields(self, request, obj=None):
        if obj is None:
            return ['name', 'members']
        if obj.kind == BillingAccount.Kind.PERSONAL:
            return ['kind', 'owner', 'balance', 'grant_link', 'created_at']
        return ['kind', 'name', 'members', 'balance', 'grant_link', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return ['kind', 'owner', 'balance', 'grant_link', 'created_at']

    @admin.display(description='Members', ordering='member_count')
    def member_count(self, account):
        return account.member_count

    @admin.display(description='Balance (credits)', ordering='balance')
    def balance(self, account):
        micro = account.balance if hasattr(account, 'balance') else account.balance_micro()
        return format_credits(micro)

    @admin.display(description='Grant')
    def grant_link(self, account):
        url = reverse('admin:billing_ledgerentry_add')
        return format_html('<a href="{}?account={}">Grant credits</a>', url, account.pk)

    # Sessions and charges will point at accounts: never delete them.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """'Add' is the grant-credits form. Charges come from chats.

    Entries are never changed or deleted.
    """
    list_display = [
        'created_at', 'account', 'kind', 'amount', 'tokens', 'price_per_1k_tokens', 'note', 'created_by',
    ]
    list_filter = ['kind', 'account']
    list_select_related = ['account__owner', 'created_by']
    readonly_fields = [
        'account', 'kind', 'amount', 'tokens', 'price_per_1k_tokens', 'note', 'created_by', 'created_at',
    ]

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = GrantForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ['account', 'amount_credits', 'note']
        return self.readonly_fields

    def get_readonly_fields(self, request, obj=None):
        return [] if obj is None else self.readonly_fields

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = {**(extra_context or {}), 'title': 'Grant credits'}
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Amount (credits)', ordering='amount_micro')
    def amount(self, entry):
        return format_credits(entry.amount_micro)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TierPrice)
class TierPriceAdmin(admin.ModelAdmin):
    list_display = ['tier', 'price_per_1k_tokens', 'updated_at']
    list_editable = ['price_per_1k_tokens']
    readonly_fields = ['tier', 'updated_at']

    # Exactly one row per tier, seeded by a migration.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
