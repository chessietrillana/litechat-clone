from django.conf import settings
from django.db import models
from django.utils import timezone

from proxy.types import Message

TITLE_WORDS = 6
TITLE_MAX_CHARS = 60
DEFAULT_TITLE = 'New chat'


def make_title(text):
    """The first few words of the first message (study NOTE Q23)."""
    words = text.split()
    if not words:
        return DEFAULT_TITLE
    title = ' '.join(words[:TITLE_WORDS])
    cut = len(words) > TITLE_WORDS
    if len(title) > TITLE_MAX_CHARS:
        title = title[:TITLE_MAX_CHARS].rstrip()
        cut = True
    return title + '…' if cut else title


class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions',
    )
    # Model and account are fixed at start (study NOTE Q20). Protected, so the
    # history of what was used (and later, charged) is never lost.
    llm_model = models.ForeignKey(
        'catalog.LLMModel', on_delete=models.PROTECT, related_name='chat_sessions',
        verbose_name='model',
    )
    billing_account = models.ForeignKey(
        'billing.BillingAccount', on_delete=models.PROTECT, related_name='chat_sessions',
    )
    title = models.CharField(max_length=100, default=DEFAULT_TITLE)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set by the chat services on every turn. The sidebar sorts by it.
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return self.title

    def history(self):
        """All messages as proxy Messages, oldest first."""
        return [Message(m.role, m.content) for m in self.messages.all()]


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    # Assistant replies only. Empty when the proxy did not report them.
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    cached_tokens = models.PositiveIntegerField(null=True, blank=True)
    finish_reason = models.CharField(max_length=20, blank=True)
    response_id = models.CharField(max_length=200, blank=True)
    # Assistant replies only. Empty when nothing was charged (no usage reported).
    # Protected: a charge is never deleted, and deleting a message keeps it.
    charge = models.OneToOneField(
        'billing.LedgerEntry', null=True, blank=True, on_delete=models.PROTECT,
        related_name='chat_message',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.get_role_display()} message in "{self.session}"'

    @property
    def was_cut_off(self):
        return self.finish_reason == 'length'

    @property
    def cost_micro(self):
        """What this reply cost in µc (a positive number), or None if not charged."""
        return -self.charge.amount_micro if self.charge_id else None
