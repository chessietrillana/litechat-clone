from decimal import Decimal
from unittest import mock

from django.db.models import ProtectedError
from django.test import TestCase, override_settings

from billing.models import BillingAccount, LedgerEntry, TierPrice
from catalog.models import Tier
from chat.models import ChatMessage, ChatSession
from chat.services import NO_PRICE, ChatError, billed_tokens, send_turn, start_session
from chat.tests.helpers import make_session, make_user, personal_account, reply, seeded_model
from proxy.errors import ProxyTimeout
from proxy.tests.helpers import load_fixture

GEMINI = 'gemini-3.8-flash'           # Value: 1 credit per 1K tokens
CLAUDE = 'claude-haiku-4-5-20251001'  # Standard: 3
GPT = 'gpt-5.6-luna'                  # Premium: 10


def charges():
    return LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CHARGE)


@mock.patch('chat.services.send_chat')
class ChargeTurnTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.account = personal_account(self.alice)

    def test_turn_is_charged_to_the_sessions_account(self, send_chat):
        session = make_session(self.alice, llm_model=seeded_model(CLAUDE))
        before = self.account.balance_micro()
        send_chat.return_value = reply(input_tokens=183, output_tokens=12)

        answer = send_turn(session, 'Hi')

        charge = charges().get()
        self.assertEqual(answer.charge, charge)
        self.assertEqual(charge.account, self.account)
        self.assertEqual(charge.created_by, self.alice)
        self.assertEqual(charge.tokens, 195)
        self.assertEqual(charge.price_per_1k_tokens, Decimal('3'))
        self.assertEqual(charge.amount_micro, -585_000)
        self.assertEqual(answer.cost_micro, 585_000)
        self.assertEqual(self.account.balance_micro(), before - 585_000)

    def test_first_turn_is_charged(self, send_chat):
        send_chat.return_value = reply(input_tokens=183, output_tokens=9)
        session = start_session(self.alice, seeded_model(GEMINI), self.account, 'Hi')
        answer = session.messages.last()
        self.assertEqual(answer.charge.tokens, 192)
        self.assertEqual(answer.charge.amount_micro, -192_000)

    def test_each_tier_uses_its_own_price(self, send_chat):
        send_chat.return_value = reply(input_tokens=900, output_tokens=100)
        for model_id, micro in ((GEMINI, 1_000_000), (CLAUDE, 3_000_000), (GPT, 10_000_000)):
            with self.subTest(model=model_id):
                session = start_session(self.alice, seeded_model(model_id), self.account, 'Hi')
                self.assertEqual(session.messages.last().cost_micro, micro)

    def test_only_input_reported_charges_input(self, send_chat):
        send_chat.return_value = reply(input_tokens=183, output_tokens=None)
        session = start_session(self.alice, seeded_model(GEMINI), self.account, 'Hi')
        self.assertEqual(session.messages.last().charge.tokens, 183)

    def test_no_usage_saves_reply_without_charge(self, send_chat):
        send_chat.return_value = reply(input_tokens=None, output_tokens=None, cached_tokens=None)
        before = self.account.balance_micro()
        session = start_session(self.alice, seeded_model(GEMINI), self.account, 'Hi')
        answer = session.messages.last()
        self.assertEqual(answer.content, 'Paris is the capital of France.')
        self.assertIsNone(answer.charge)
        self.assertIsNone(answer.cost_micro)
        self.assertFalse(charges().exists())
        self.assertEqual(self.account.balance_micro(), before)

    def test_proxy_failure_charges_nothing(self, send_chat):
        session = make_session(self.alice, turns=1)
        before = self.account.balance_micro()
        send_chat.side_effect = ProxyTimeout('timed out')
        with self.assertRaises(ProxyTimeout):
            send_turn(session, 'Hi')
        self.assertEqual(session.messages.count(), 2)
        self.assertFalse(charges().exists())
        self.assertEqual(self.account.balance_micro(), before)

    def test_failed_charge_saves_no_messages(self, send_chat):
        send_chat.return_value = reply()
        session = make_session(self.alice, turns=1)
        with mock.patch('chat.services.record_charge', side_effect=RuntimeError('db down')):
            with self.assertRaises(RuntimeError):
                send_turn(session, 'Hi')
            with self.assertRaises(RuntimeError):
                start_session(self.alice, seeded_model(GEMINI), self.account, 'Hi')
        self.assertEqual(session.messages.count(), 2)
        self.assertEqual(ChatSession.objects.count(), 1)

    def test_each_charge_keeps_its_own_price(self, send_chat):
        send_chat.return_value = reply(input_tokens=500, output_tokens=500)
        session = make_session(self.alice, llm_model=seeded_model(CLAUDE))
        send_turn(session, 'one')
        TierPrice.objects.filter(tier=Tier.STANDARD).update(price_per_1k_tokens=Decimal('5'))
        send_turn(session, 'two')
        prices = list(charges().order_by('id').values_list('price_per_1k_tokens', 'amount_micro'))
        self.assertEqual(prices, [(Decimal('3'), -3_000_000), (Decimal('5'), -5_000_000)])

    def test_price_edit_while_waiting_does_not_change_the_turn(self, send_chat):
        def edit_price_then_reply(*args):
            TierPrice.objects.filter(tier=Tier.STANDARD).update(price_per_1k_tokens=Decimal('5'))
            return reply(input_tokens=500, output_tokens=500)
        send_chat.side_effect = edit_price_then_reply
        send_turn(make_session(self.alice, llm_model=seeded_model(CLAUDE)), 'Hi')
        self.assertEqual(charges().get().price_per_1k_tokens, Decimal('3'))

    def test_missing_price_is_refused_before_sending(self, send_chat):
        TierPrice.objects.filter(tier=Tier.VALUE).delete()
        with self.assertRaises(ChatError) as caught:
            start_session(self.alice, seeded_model(GEMINI), self.account, 'Hi')
        self.assertEqual(caught.exception.user_message, NO_PRICE)
        send_chat.assert_not_called()
        self.assertFalse(ChatSession.objects.exists())

    def test_shared_account_charge_names_the_member(self, send_chat):
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Team')
        team.members.add(self.alice)
        LedgerEntry.objects.create(account=team, amount_micro=5_000_000, kind='admin_grant')
        send_chat.return_value = reply(input_tokens=183, output_tokens=12)
        start_session(self.alice, seeded_model(CLAUDE), team, 'Hi')
        charge = charges().get()
        self.assertEqual(charge.account, team)
        self.assertEqual(charge.created_by, self.alice)
        self.assertEqual(team.balance_micro(), 5_000_000 - 585_000)

    def test_charges_outlive_their_messages(self, send_chat):
        send_chat.return_value = reply()
        session = start_session(self.alice, seeded_model(GEMINI), self.account, 'Hi')
        charge = session.messages.last().charge
        session.delete()
        self.assertTrue(LedgerEntry.objects.filter(pk=charge.pk).exists())
        with self.assertRaises(ProtectedError):
            charge.account.delete()


@override_settings(PROXY_KEYS={'openai': 'k1', 'anthropic': 'k2', 'google': 'k3'})
class AnthropicCacheChargeTests(TestCase):
    """Real adapter parsing; only the HTTP call is mocked."""

    @mock.patch('proxy.client.transport.post_json')
    def test_cache_reads_and_writes_are_billed_as_input(self, post_json):
        post_json.return_value = (200, load_fixture('synthetic_anthropic_cache_tokens.json'))
        alice = make_user('alice')
        session = start_session(alice, seeded_model(CLAUDE), personal_account(alice), 'Hi')
        answer = session.messages.last()
        self.assertEqual(answer.input_tokens, 278)  # 100 + 128 read + 50 written
        self.assertEqual(answer.charge.tokens, 290)  # + 12 out
        self.assertEqual(answer.cost_micro, 870_000)


class BilledTokensTests(TestCase):
    def test_counts(self):
        self.assertEqual(billed_tokens(reply(input_tokens=183, output_tokens=12)), 195)
        self.assertEqual(billed_tokens(reply(input_tokens=None, output_tokens=12)), 12)
        self.assertEqual(billed_tokens(reply(input_tokens=0, output_tokens=0)), 0)
        self.assertIsNone(billed_tokens(reply(input_tokens=None, output_tokens=None)))

    def test_message_without_charge_has_no_cost(self):
        self.assertIsNone(ChatMessage(role='assistant', content='x').cost_micro)
