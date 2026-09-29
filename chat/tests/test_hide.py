from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from billing.models import LedgerEntry
from chat.models import ChatMessage, ChatSession
from chat.services import CHAT_DELETED, ChatError, send_turn, start_session
from chat.tests.helpers import make_session, make_user, personal_account, reply, seeded_model


class HideTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')

    def test_hide_sets_hidden_at_only(self):
        session = make_session(self.alice, title='Capitals')
        updated_at = session.updated_at
        session.hide()
        session.refresh_from_db()
        self.assertIsNotNone(session.hidden_at)
        self.assertTrue(session.is_hidden)
        self.assertEqual(session.title, 'Capitals')
        self.assertEqual(session.updated_at, updated_at)

    def test_visible_leaves_out_hidden_chats(self):
        kept = make_session(self.alice, title='Kept')
        make_session(self.alice, title='Gone').hide()
        self.assertEqual(list(ChatSession.objects.visible()), [kept])
        self.assertEqual(list(self.alice.chat_sessions.visible()), [kept])
        self.assertEqual(ChatSession.objects.count(), 2)

    @mock.patch('chat.services.send_chat')
    def test_hiding_keeps_messages_and_charges(self, send_chat):
        send_chat.return_value = reply()
        account = personal_account(self.alice)
        session = start_session(self.alice, seeded_model(), account, 'Hi')
        balance = account.balance_micro()
        session.hide()
        self.assertEqual(session.messages.count(), 2)
        self.assertEqual(LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CHARGE).count(), 1)
        self.assertEqual(account.balance_micro(), balance)

    @mock.patch('chat.services.send_chat')
    def test_send_turn_refuses_a_hidden_chat(self, send_chat):
        session = make_session(self.alice, turns=1)
        session.hide()
        with self.assertRaises(ChatError) as caught:
            send_turn(session, 'Hi')
        self.assertEqual(caught.exception.user_message, CHAT_DELETED)
        send_chat.assert_not_called()
        self.assertEqual(session.messages.count(), 2)


@mock.patch('chat.services.send_chat')
class HiddenChatPageTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.client.force_login(self.alice)
        self.kept = make_session(self.alice, title='Kept chat')
        self.gone = make_session(self.alice, title='Gone chat', turns=1)
        self.gone.hide()

    def test_sidebar_leaves_out_hidden_chat(self, send_chat):
        response = self.client.get('/')
        self.assertContains(response, 'Kept chat')
        self.assertNotContains(response, 'Gone chat')
        self.assertNotContains(response, f'/chat/{self.gone.pk}/')

    def test_get_is_404(self, send_chat):
        self.assertEqual(self.client.get(f'/chat/{self.gone.pk}/').status_code, 404)

    def test_post_is_404_and_sends_nothing(self, send_chat):
        response = self.client.post(f'/chat/{self.gone.pk}/', {'message': 'Hi'})
        self.assertEqual(response.status_code, 404)
        send_chat.assert_not_called()
        self.assertEqual(self.gone.messages.count(), 2)
        self.assertFalse(LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CHARGE).exists())

    def test_visible_chat_still_opens(self, send_chat):
        self.assertEqual(self.client.get(f'/chat/{self.kept.pk}/').status_code, 200)


class HiddenChatAdminTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser('admin', password='correct-horse-42')
        alice = make_user('alice')
        make_session(alice, title='Kept chat')
        self.gone = make_session(alice, title='Gone chat', turns=1)
        self.gone.hide()
        self.client.force_login(admin)

    def test_list_shows_column_and_filter(self):
        response = self.client.get('/admin/chat/chatsession/')
        self.assertContains(response, 'Hidden at')
        self.assertContains(response, 'By deleted by user')
        self.assertContains(response, 'Gone chat')

    def test_filter(self):
        yes = self.client.get('/admin/chat/chatsession/?deleted=yes')
        self.assertContains(yes, 'Gone chat')
        self.assertNotContains(yes, 'Kept chat')
        no = self.client.get('/admin/chat/chatsession/?deleted=no')
        self.assertContains(no, 'Kept chat')
        self.assertNotContains(no, 'Gone chat')

    def test_hidden_chat_page_still_opens(self):
        response = self.client.get(f'/admin/chat/chatsession/{self.gone.pk}/change/')
        self.assertContains(response, 'question 1')
        self.assertEqual(ChatMessage.objects.filter(session=self.gone).count(), 2)
