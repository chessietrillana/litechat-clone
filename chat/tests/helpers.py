from django.contrib.auth.models import User

from billing.models import BillingAccount
from catalog.models import LLMModel
from chat.models import ChatMessage, ChatSession
from proxy.types import ChatResult

PASSWORD = 'correct-horse-42'


def make_user(username):
    # The billing signal gives every new user a personal account with 1,000 credits.
    return User.objects.create_user(username, password=PASSWORD)


def personal_account(user):
    return BillingAccount.objects.get(kind=BillingAccount.Kind.PERSONAL, owner=user)


def seeded_model(proxy_model_id='gemini-3.8-flash'):
    return LLMModel.objects.get(proxy_model_id=proxy_model_id)


def make_session(user, title='Test chat', turns=0, llm_model=None, account=None):
    session = ChatSession.objects.create(
        user=user,
        llm_model=llm_model or seeded_model(),
        billing_account=account or personal_account(user),
        title=title,
    )
    for n in range(1, turns + 1):
        ChatMessage.objects.create(session=session, role='user', content=f'question {n}')
        ChatMessage.objects.create(session=session, role='assistant', content=f'answer {n}')
    return session


def reply(text='Paris is the capital of France.', finish_reason='stop', input_tokens=183,
          output_tokens=9, cached_tokens=0, response_id='resp-1'):
    return ChatResult(
        text=text, input_tokens=input_tokens, output_tokens=output_tokens,
        cached_tokens=cached_tokens, finish_reason=finish_reason,
        raw_finish_reason=finish_reason, response_id=response_id, model='test-model',
    )
