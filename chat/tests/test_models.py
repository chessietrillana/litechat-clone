from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase

from billing.models import BillingAccount
from chat.models import ChatMessage, ChatSession, make_title
from chat.tests.helpers import make_session, make_user, seeded_model
from proxy.types import Message


class MakeTitleTests(TestCase):
    def test_short_message_is_kept(self):
        self.assertEqual(
            make_title('What is the capital of France?'), 'What is the capital of France?'
        )

    def test_long_message_keeps_first_six_words(self):
        self.assertEqual(
            make_title('Please tell me the capital city of France today'),
            'Please tell me the capital city…',
        )

    def test_one_long_word_is_cut_at_60_characters(self):
        self.assertEqual(make_title('a' * 100), 'a' * 60 + '…')

    def test_line_breaks_become_spaces(self):
        self.assertEqual(make_title('Hello\nthere\r\n\tfriend'), 'Hello there friend')

    def test_blank_message_gives_default(self):
        self.assertEqual(make_title('   \n '), 'New chat')


class ChatSessionTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')

    def test_messages_come_back_in_order(self):
        session = make_session(self.alice, turns=2)
        self.assertEqual(
            [m.content for m in session.messages.all()],
            ['question 1', 'answer 1', 'question 2', 'answer 2'],
        )

    def test_history_gives_proxy_messages(self):
        session = make_session(self.alice, turns=1)
        self.assertEqual(
            session.history(),
            [Message('user', 'question 1'), Message('assistant', 'answer 1')],
        )

    def test_cut_off_flag(self):
        session = make_session(self.alice)
        message = ChatMessage.objects.create(
            session=session, role='assistant', content='Partial', finish_reason='length',
        )
        self.assertTrue(message.was_cut_off)

    def test_model_with_session_cannot_be_deleted(self):
        make_session(self.alice)
        with self.assertRaises(ProtectedError):
            seeded_model().delete()

    def test_billing_account_with_session_cannot_be_deleted(self):
        # A shared account with no ledger entries, so only the session protects it.
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Team')
        team.members.add(self.alice)
        session = make_session(self.alice, account=team)
        with self.assertRaises(ProtectedError):
            team.delete()
        self.assertTrue(ChatSession.objects.filter(pk=session.pk).exists())


class ChatSessionAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', password='correct-horse-42')
        self.alice = make_user('alice')
        self.session = make_session(self.alice, title='Capitals', turns=1)
        self.client.force_login(self.admin)

    def test_list_loads(self):
        response = self.client.get('/admin/chat/chatsession/')
        self.assertContains(response, 'Capitals')
        self.assertNotContains(response, 'Add chat session')

    def test_session_page_shows_messages_read_only(self):
        response = self.client.get(f'/admin/chat/chatsession/{self.session.pk}/change/')
        self.assertContains(response, 'question 1')
        self.assertContains(response, 'answer 1')
        self.assertNotContains(response, 'name="_save"')

    def test_no_add_or_delete(self):
        self.assertEqual(self.client.get('/admin/chat/chatsession/add/').status_code, 403)
        response = self.client.get(f'/admin/chat/chatsession/{self.session.pk}/delete/')
        self.assertEqual(response.status_code, 403)
