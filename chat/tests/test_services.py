from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from billing.models import BillingAccount, LedgerEntry
from chat import services
from chat.models import ChatMessage, ChatSession
from chat.services import ChatError, send_turn, start_session
from chat.tests.helpers import make_session, make_user, personal_account, reply, seeded_model
from proxy.errors import ProxyTimeout
from proxy.types import Message


@mock.patch('chat.services.send_chat')
class StartSessionTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.account = personal_account(self.alice)
        self.model = seeded_model('gemini-3.8-flash')

    def test_saves_session_title_and_both_messages(self, send_chat):
        send_chat.return_value = reply()
        session = start_session(self.alice, self.model, self.account, 'What is the capital of France?')

        send_chat.assert_called_once_with(
            'google', 'gemini-3.8-flash', [Message('user', 'What is the capital of France?')],
        )
        self.assertEqual(session.title, 'What is the capital of France?')
        self.assertEqual(session.user, self.alice)
        self.assertEqual(session.llm_model, self.model)
        self.assertEqual(session.billing_account, self.account)
        question, answer = session.messages.all()
        self.assertEqual((question.role, question.content), ('user', 'What is the capital of France?'))
        self.assertEqual((answer.role, answer.content), ('assistant', 'Paris is the capital of France.'))
        self.assertEqual(
            (answer.input_tokens, answer.output_tokens, answer.cached_tokens), (183, 9, 0),
        )
        self.assertEqual(answer.finish_reason, 'stop')
        self.assertEqual(answer.response_id, 'resp-1')
        self.assertIsNone(question.input_tokens)

    def test_missing_usage_is_saved_as_empty(self, send_chat):
        send_chat.return_value = reply(input_tokens=None, output_tokens=None, cached_tokens=None,
                                       response_id=None)
        session = start_session(self.alice, self.model, self.account, 'Hi')
        answer = session.messages.last()
        self.assertIsNone(answer.input_tokens)
        self.assertEqual(answer.response_id, '')

    def test_proxy_failure_saves_nothing(self, send_chat):
        send_chat.side_effect = ProxyTimeout('timed out')
        with self.assertRaises(ProxyTimeout):
            start_session(self.alice, self.model, self.account, 'Hi')
        self.assertFalse(ChatSession.objects.exists())
        self.assertFalse(ChatMessage.objects.exists())

    def test_empty_reply_without_usage_saves_nothing(self, send_chat):
        send_chat.return_value = reply(text='  \n', input_tokens=None, output_tokens=None)
        with self.assertRaisesMessage(ChatError, services.EMPTY_REPLY):
            start_session(self.alice, self.model, self.account, 'Hi')
        self.assertFalse(ChatSession.objects.exists())
        self.assertFalse(LedgerEntry.objects.filter(kind='charge').exists())

    def test_empty_reply_with_usage_is_saved_and_charged(self, send_chat):
        send_chat.return_value = reply(text='  \n', input_tokens=183, output_tokens=0)
        session = start_session(self.alice, self.model, self.account, 'Hi')
        question, answer = session.messages.all()
        self.assertEqual(question.content, 'Hi')
        self.assertTrue(answer.is_empty_reply)
        self.assertEqual(answer.charge.tokens, 183)

        # The next send leaves the empty turn out: its history is just the new message.
        send_chat.return_value = reply()
        send_turn(session, 'Hello?')
        self.assertEqual(send_chat.call_args.args[2], [Message('user', 'Hello?')])

    def test_turned_off_model_is_refused_before_sending(self, send_chat):
        self.model.is_active = False
        self.model.save()
        with self.assertRaisesMessage(ChatError, services.MODEL_OFF):
            start_session(self.alice, self.model, self.account, 'Hi')
        send_chat.assert_not_called()

    def test_other_users_account_is_refused_before_sending(self, send_chat):
        bob = make_user('bob')
        with self.assertRaisesMessage(ChatError, services.ACCOUNT_NOT_ALLOWED):
            start_session(self.alice, self.model, personal_account(bob), 'Hi')
        send_chat.assert_not_called()

    def test_shared_account_needs_membership(self, send_chat):
        send_chat.return_value = reply()
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Team')
        LedgerEntry.objects.create(account=team, amount_micro=5_000_000, kind='admin_grant')
        with self.assertRaisesMessage(ChatError, services.ACCOUNT_NOT_ALLOWED):
            start_session(self.alice, self.model, team, 'Hi')
        team.members.add(self.alice)
        session = start_session(self.alice, self.model, team, 'Hi')
        self.assertEqual(session.billing_account, team)

    def test_blank_and_too_long_text_are_refused(self, send_chat):
        with self.assertRaisesMessage(ChatError, services.BLANK_MESSAGE):
            start_session(self.alice, self.model, self.account, '  \n ')
        with self.assertRaisesMessage(ChatError, services.TOO_LONG):
            start_session(self.alice, self.model, self.account, 'a' * 20_001)
        send_chat.assert_not_called()

    def test_longest_allowed_text_is_sent(self, send_chat):
        send_chat.return_value = reply()
        start_session(self.alice, self.model, self.account, 'a' * 20_000)
        send_chat.assert_called_once()


@mock.patch('chat.services.send_chat')
class SendTurnTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.session = make_session(self.alice, llm_model=seeded_model('gpt-5.6-luna'), turns=3)

    def test_sends_full_history_in_order(self, send_chat):
        send_chat.return_value = reply(text='answer 4')
        send_turn(self.session, 'question 4')

        interface, model_id, history = send_chat.call_args.args
        self.assertEqual((interface, model_id), ('openai', 'gpt-5.6-luna'))
        self.assertEqual(len(history), 7)
        self.assertEqual(history[0], Message('user', 'question 1'))
        self.assertEqual(history[5], Message('assistant', 'answer 3'))
        self.assertEqual(history[6], Message('user', 'question 4'))
        self.assertEqual(self.session.messages.count(), 8)
        self.assertEqual(self.session.messages.last().content, 'answer 4')

    def test_empty_reply_turn_is_left_out_of_later_history(self, send_chat):
        send_chat.return_value = reply(text='', input_tokens=190, output_tokens=0)
        send_turn(self.session, 'question 4')
        self.assertEqual(self.session.messages.count(), 8)

        send_chat.return_value = reply(text='answer 5')
        send_turn(self.session, 'question 5')
        history = send_chat.call_args.args[2]
        self.assertEqual(len(history), 7)
        self.assertEqual(history[5], Message('assistant', 'answer 3'))
        self.assertEqual(history[6], Message('user', 'question 5'))

    def test_returns_the_reply(self, send_chat):
        send_chat.return_value = reply(text='answer 4', finish_reason='length')
        answer = send_turn(self.session, 'question 4')
        self.assertEqual(answer.role, 'assistant')
        self.assertTrue(answer.was_cut_off)

    def test_updates_updated_at(self, send_chat):
        send_chat.return_value = reply()
        old = timezone.now() - timedelta(days=1)
        ChatSession.objects.filter(pk=self.session.pk).update(updated_at=old)
        self.session.refresh_from_db()
        send_turn(self.session, 'question 4')
        self.session.refresh_from_db()
        self.assertGreater(self.session.updated_at, old)

    def test_proxy_failure_saves_nothing(self, send_chat):
        send_chat.side_effect = ProxyTimeout('timed out')
        old = self.session.updated_at
        with self.assertRaises(ProxyTimeout):
            send_turn(self.session, 'question 4')
        self.session.refresh_from_db()
        self.assertEqual(self.session.messages.count(), 6)
        self.assertEqual(self.session.updated_at, old)

    def test_turned_off_model_is_refused(self, send_chat):
        self.session.llm_model.is_active = False
        self.session.llm_model.save()
        with self.assertRaisesMessage(ChatError, services.MODEL_OFF):
            send_turn(self.session, 'question 4')
        send_chat.assert_not_called()

    def test_removed_from_shared_account_is_refused(self, send_chat):
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Team')
        team.members.add(self.alice)
        session = make_session(self.alice, account=team, turns=1)
        team.members.remove(self.alice)
        with self.assertRaisesMessage(ChatError, services.ACCOUNT_NOT_ALLOWED):
            send_turn(session, 'question 2')
        send_chat.assert_not_called()
        self.assertEqual(session.messages.count(), 2)
