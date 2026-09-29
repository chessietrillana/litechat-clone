from django import forms

from billing.models import BillingAccount
from billing.units import format_credits
from catalog.models import LLMModel
from chat.services import MAX_MESSAGE_CHARS


class ModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, llm_model):
        return (f'{llm_model.display_name} ({llm_model.get_provider_display()}, '
                f'{llm_model.get_tier_display()})')


class AccountChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, account):
        return f'{account} · {format_credits(account.balance)} credits'


def message_field():
    return forms.CharField(
        label='Message',
        max_length=MAX_MESSAGE_CHARS,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type a message'}),
        error_messages={'required': 'Type a message first.'},
    )


class MessageForm(forms.Form):
    message = message_field()


class NewChatForm(forms.Form):
    """Model, billing account, and first message. Only choices the user may use."""
    llm_model = ModelChoiceField(
        label='Model', queryset=LLMModel.objects.none(), empty_label=None,
    )
    billing_account = AccountChoiceField(
        label='Billing account', queryset=BillingAccount.objects.none(), empty_label=None,
    )
    message = message_field()

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['llm_model'].queryset = LLMModel.objects.active()
        self.fields['billing_account'].queryset = (
            BillingAccount.objects.for_user(user).with_balance().select_related('owner')
        )
