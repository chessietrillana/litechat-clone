from decimal import Decimal

from django import forms

from billing.models import BillingAccount, LedgerEntry
from billing.units import credits_to_micro


class BillingAccountForm(forms.ModelForm):
    """Admin form. New accounts are always shared (personal ones are automatic)."""

    class Meta:
        model = BillingAccount
        fields = ['name', 'members']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            self.instance.kind = BillingAccount.Kind.SHARED

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if self.instance.kind == BillingAccount.Kind.SHARED and not name:
            raise forms.ValidationError('A shared account needs a name.')
        return name


class GrantForm(forms.ModelForm):
    """Admin 'grant credits' form: the amount is typed in credits and stored in µc."""

    amount_credits = forms.DecimalField(
        label='Amount (credits)', max_digits=18, decimal_places=6,
        help_text='Credits to add. More than 0, up to 6 decimals.',
    )

    class Meta:
        model = LedgerEntry
        fields = ['account', 'amount_credits', 'note']

    def clean_amount_credits(self):
        amount = self.cleaned_data['amount_credits']
        if amount <= Decimal('0'):
            raise forms.ValidationError('The amount must be more than 0.')
        return amount

    def save(self, commit=True):
        self.instance.amount_micro = credits_to_micro(self.cleaned_data['amount_credits'])
        self.instance.kind = LedgerEntry.Kind.ADMIN_GRANT
        return super().save(commit)
