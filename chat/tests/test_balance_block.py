from unittest import mock

from django.test import TestCase

from billing.models import LedgerEntry
from chat.models import ChatSession
from chat.services import NO_CREDITS, ChatError, send_turn, start_session
from chat.tests.helpers import make_session, make_user, personal_account, reply, seeded_model, set_balance

BLOCKED_NOTE = 'This billing account has no credits left, so sending is blocked.'
BELOW_ZERO_NOTE = 'one reply can take the balance below 0'


@mock.patch('chat.services.send_chat')
class BalanceBlockServiceTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.account = personal_account(self.alice)
        self.session = make_session(self.alice, turns=1)

    def assert_blocked(self, send_chat):
        count = self.session.messages.count()
        with self.assertRaises(ChatError) as caught:
            send_turn(self.session, 'Hi')
        self.assertEqual(caught.exception.user_message, NO_CREDITS)
        send_chat.assert_not_called()
        self.assertEqual(self.session.messages.count(), count)

    def test_balance_of_zero_is_blocked_before_sending(self, send_chat):
        set_balance(self.account, 0)
        self.assert_blocked(send_chat)

    def test_negative_balance_is_blocked(self, send_chat):
        set_balance(self.account, -5)
        self.assert_blocked(send_chat)

    def test_one_micro_credit_is_enough_to_send(self, send_chat):
        set_balance(self.account, 1)
        send_chat.return_value = reply()
        send_turn(self.session, 'Hi')
        self.assertEqual(self.session.messages.count(), 4)

    def test_a_turn_can_go_below_zero_then_the_next_is_blocked(self, send_chat):
        set_balance(self.account, 100_000)  # 0.1 credits
        send_chat.return_value = reply(input_tokens=183, output_tokens=9)  # 0.192 credits on Value
        send_turn(self.session, 'Hi')
        self.assertEqual(self.account.balance_micro(), 100_000 - 192_000)
        send_chat.reset_mock()
        self.assert_blocked(send_chat)

    def test_a_grant_lets_sending_start_again(self, send_chat):
        set_balance(self.account, 0)
        self.assert_blocked(send_chat)
        LedgerEntry.objects.create(account=self.account, amount_micro=10_000_000, kind='admin_grant')
        send_chat.return_value = reply()
        send_turn(self.session, 'Hi')
        self.assertEqual(self.session.messages.count(), 4)

    def test_new_chat_is_blocked_too(self, send_chat):
        set_balance(self.account, 0)
        with self.assertRaisesMessage(ChatError, NO_CREDITS):
            start_session(self.alice, seeded_model(), self.account, 'Hi')
        send_chat.assert_not_called()


@mock.patch('chat.services.send_chat')
class BalanceBlockPageTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.account = personal_account(self.alice)
        self.client.force_login(self.alice)
        self.session = make_session(self.alice, turns=1)
        self.url = f'/chat/{self.session.pk}/'

    def test_page_with_credits_has_the_input_box(self, send_chat):
        response = self.client.get(self.url)
        self.assertContains(response, '<textarea')
        self.assertNotContains(response, BLOCKED_NOTE)

    def test_page_at_zero_shows_note_instead_of_input_box(self, send_chat):
        set_balance(self.account, 0)
        response = self.client.get(self.url)
        self.assertContains(response, BLOCKED_NOTE)
        self.assertContains(response, BELOW_ZERO_NOTE)
        self.assertNotContains(response, '<textarea')
        self.assertNotContains(response, 'data-chat-form')

    def test_post_anyway_is_refused(self, send_chat):
        set_balance(self.account, -1)
        response = self.client.post(self.url, {'message': 'Hi'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, BLOCKED_NOTE)
        self.assertNotContains(response, 'role="alert"')  # not said twice
        send_chat.assert_not_called()
        self.assertEqual(self.session.messages.count(), 2)

    def test_new_chat_with_empty_account_shows_error_and_keeps_text(self, send_chat):
        set_balance(self.account, 0)
        response = self.client.post('/chat/new/', {
            'llm_model': seeded_model().pk, 'billing_account': self.account.pk, 'message': 'Keep me',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This billing account has no credits left.')
        self.assertContains(response, 'Keep me</textarea>')
        send_chat.assert_not_called()
        self.assertEqual(ChatSession.objects.count(), 1)
