from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from billing.charges import record_charge
from billing.models import TierPrice
from chat.models import ChatMessage
from chat.tests.helpers import make_session, make_user


def add_turn(session, input_tokens, output_tokens, charged=True):
    ChatMessage.objects.create(session=session, role='user', content='question')
    charge = None
    if charged:
        tier_price = TierPrice.objects.get(tier=session.llm_model.tier)
        charge = record_charge(session.billing_account, session.user, input_tokens + output_tokens, tier_price)
    ChatMessage.objects.create(
        session=session, role='assistant', content='answer',
        input_tokens=input_tokens if charged else None,
        output_tokens=output_tokens if charged else None, charge=charge,
    )


class SessionUsageDisplayTests(TestCase):
    """The seeded Gemini model is Value tier: 1 credit per 1K tokens."""

    def setUp(self):
        self.alice = make_user('alice')
        self.client.force_login(self.alice)
        self.session = make_session(self.alice)
        self.url = f'/chat/{self.session.pk}/'

    def test_each_reply_shows_tokens_and_cost(self):
        add_turn(self.session, 1830, 120)
        response = self.client.get(self.url)
        self.assertContains(response, '1,830 in · 120 out · 1.95 credits')

    def test_reply_without_usage_says_not_charged(self):
        add_turn(self.session, 0, 0, charged=False)
        self.assertContains(self.client.get(self.url), 'No usage reported · not charged')

    def test_header_shows_balance_and_totals(self):
        add_turn(self.session, 1830, 120)   # 1.95 credits
        add_turn(self.session, 2000, 50)    # 2.05 credits
        response = self.client.get(self.url)
        self.assertContains(response, 'This chat: 4,000 tokens · 4 credits')
        self.assertContains(response, 'billed to alice (personal), balance 996 credits')
        self.assertContains(response, 'one reply can take the balance below 0')

    def test_chat_with_no_charges_shows_zero(self):
        self.assertContains(self.client.get(self.url), 'This chat: 0 tokens · 0 credits')

    def test_user_bubbles_have_no_usage_line(self):
        add_turn(self.session, 100, 10)
        self.assertEqual(self.client.get(self.url).content.decode().count('bubble-usage'), 1)

    def test_query_count_does_not_grow_with_messages(self):
        add_turn(self.session, 100, 10)
        one_turn = self.count_page_queries()
        for n in range(5):
            add_turn(self.session, 100, 10, charged=n % 2 == 0)
        self.assertEqual(self.count_page_queries(), one_turn)

    def count_page_queries(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(self.url).status_code, 200)
        return len(queries)
