"""Start a chat and send turns. The only chat code that calls the proxy.

A turn is saved only when the proxy answers. The proxy call runs outside the
database transaction, so the database is not locked while we wait.
"""
from django.db import transaction
from django.utils import timezone

from billing.models import BillingAccount
from chat.models import ChatMessage, ChatSession, make_title
from proxy.client import send_chat
from proxy.types import Message

MAX_MESSAGE_CHARS = 20_000

MODEL_OFF = 'This model has been turned off. Start a new chat with another model.'
ACCOUNT_NOT_ALLOWED = 'You can no longer use this billing account. Start a new chat.'
BLANK_MESSAGE = 'Type a message first.'
TOO_LONG = f'Messages can be at most {MAX_MESSAGE_CHARS:,} characters.'
EMPTY_REPLY = 'The model sent an empty reply. Please try again.'


class ChatError(Exception):
    """A send we refuse. `user_message` is safe to show."""

    def __init__(self, user_message):
        self.user_message = user_message
        super().__init__(user_message)


def check_text(text):
    if not text or not text.strip():
        raise ChatError(BLANK_MESSAGE)
    if len(text) > MAX_MESSAGE_CHARS:
        raise ChatError(TOO_LONG)


def check_can_send(user, llm_model, billing_account):
    if not llm_model.is_active:
        raise ChatError(MODEL_OFF)
    if not BillingAccount.objects.for_user(user).filter(pk=billing_account.pk).exists():
        raise ChatError(ACCOUNT_NOT_ALLOWED)


def start_session(user, llm_model, billing_account, text):
    """Send the first message. Return the new session, made only if the proxy answers."""
    check_text(text)
    check_can_send(user, llm_model, billing_account)
    result = _ask(llm_model, [Message(ChatMessage.Role.USER, text)])
    with transaction.atomic():
        session = ChatSession.objects.create(
            user=user, llm_model=llm_model, billing_account=billing_account,
            title=make_title(text),
        )
        return _save_turn(session, text, result)[0]


def send_turn(session, text):
    """Send the next message with the full history (study NOTE Q22). Return the reply."""
    check_text(text)
    check_can_send(session.user, session.llm_model, session.billing_account)
    history = session.history() + [Message(ChatMessage.Role.USER, text)]
    result = _ask(session.llm_model, history)
    with transaction.atomic():
        return _save_turn(session, text, result)[1]


def _ask(llm_model, history):
    # ProxyError is passed on unchanged. The view shows its user_message.
    result = send_chat(llm_model.provider, llm_model.proxy_model_id, history)
    if not result.text.strip():
        # An empty reply would break the next turn's history, so it is not saved.
        raise ChatError(EMPTY_REPLY)
    return result


def _save_turn(session, text, result):
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=text)
    reply = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cached_tokens=result.cached_tokens,
        finish_reason=result.finish_reason,
        response_id=result.response_id or '',
    )
    session.updated_at = timezone.now()
    session.save(update_fields=['updated_at'])
    return session, reply
