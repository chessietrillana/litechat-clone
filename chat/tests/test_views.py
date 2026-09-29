from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from billing.models import BillingAccount, LedgerEntry
from chat.models import ChatSession
from chat.tests.helpers import make_session, make_user, personal_account, reply, seeded_model
from proxy.errors import ProxyTimeout


class HomePageTests(TestCase):
    """The home page is the new chat page (moved from config/tests.py)."""

    def setUp(self):
        self.alice = make_user('alice')
        self.bob = make_user('bob')

    def get_home(self, user):
        self.client.force_login(user)
        return self.client.get('/')

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get('/')
        self.assertRedirects(response, '/accounts/login/?next=/', fetch_redirect_response=False)

    def test_shows_greeting_new_chat_button_and_form(self):
        response = self.get_home(self.alice)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello, alice.')
        self.assertContains(response, '<a class="button new-chat" href="/">New chat</a>', html=True)
        self.assertContains(response, 'action="/chat/new/"')
        self.assertContains(response, 'No chats yet.')

    def test_model_picker_lists_only_active_models(self):
        gpt = seeded_model('gpt-5.6-luna')
        gpt.is_active = False
        gpt.save()
        response = self.get_home(self.alice)
        self.assertContains(response, 'Gemini 3.8 Flash (Google, Value)')
        self.assertContains(response, 'Claude Haiku 4.5 (Anthropic, Standard)')
        self.assertNotContains(response, 'GPT-5.6 Luna')

    def test_new_user_sees_personal_account_with_signup_credits(self):
        response = self.get_home(self.alice)
        self.assertContains(response, 'alice (personal) · 1,000 credits')

    def test_member_sees_shared_account_but_not_others(self):
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Study group')
        team.members.add(self.alice)
        LedgerEntry.objects.create(account=team, amount_micro=500_000_000, kind=LedgerEntry.Kind.ADMIN_GRANT)
        BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Secret club')

        response = self.get_home(self.alice)
        self.assertContains(response, 'Study group · 500 credits')
        self.assertNotContains(response, 'Secret club')
        self.assertNotContains(response, 'bob (personal)')

        response = self.get_home(self.bob)
        self.assertContains(response, 'bob (personal) · 1,000 credits')
        self.assertNotContains(response, 'Study group')
        self.assertNotContains(response, 'alice (personal)')

    def test_post_to_home_is_not_allowed(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post('/').status_code, 405)


class SidebarTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.client.force_login(self.alice)

    def test_lists_own_sessions_newest_activity_first(self):
        now = timezone.now()
        old = make_session(self.alice, title='Old chat')
        new = make_session(self.alice, title='New chat about Rome')
        ChatSession.objects.filter(pk=old.pk).update(updated_at=now)
        ChatSession.objects.filter(pk=new.pk).update(updated_at=now - timedelta(hours=1))
        make_session(make_user('bob'), title='Bob chat')

        content = self.client.get('/').content.decode()
        self.assertLess(content.index('Old chat'), content.index('New chat about Rome'))
        self.assertNotIn('Bob chat', content)
        self.assertIn(f'href="/chat/{old.pk}/"', content)

    def test_current_session_is_marked(self):
        session = make_session(self.alice, title='Capitals')
        response = self.client.get(f'/chat/{session.pk}/')
        self.assertContains(response, 'aria-current="page"', count=1)


@mock.patch('chat.services.send_chat')
class NewChatTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.client.force_login(self.alice)
        self.model = seeded_model('claude-haiku-4-5-20251001')
        self.account = personal_account(self.alice)

    def post(self, **overrides):
        data = {
            'llm_model': self.model.pk,
            'billing_account': self.account.pk,
            'message': 'What is the capital of France?',
            **overrides,
        }
        return self.client.post('/chat/new/', data)

    def test_starts_session_and_redirects(self, send_chat):
        send_chat.return_value = reply()
        response = self.post()
        session = ChatSession.objects.get()
        self.assertRedirects(response, f'/chat/{session.pk}/')
        self.assertEqual(session.llm_model, self.model)
        self.assertEqual(session.messages.count(), 2)
        self.assertEqual(send_chat.call_args.args[0], 'anthropic')

    def test_other_users_account_is_a_form_error(self, send_chat):
        bob = make_user('bob')
        response = self.post(billing_account=personal_account(bob).pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.assertFalse(ChatSession.objects.exists())
        send_chat.assert_not_called()

    def test_turned_off_model_is_a_form_error(self, send_chat):
        self.model.is_active = False
        self.model.save()
        response = self.post()
        self.assertContains(response, 'Select a valid choice')
        self.assertFalse(ChatSession.objects.exists())
        send_chat.assert_not_called()

    def test_blank_message_is_a_form_error(self, send_chat):
        response = self.post(message='   ')
        self.assertContains(response, 'Type a message first.')
        send_chat.assert_not_called()

    def test_proxy_failure_shows_error_and_keeps_text(self, send_chat):
        send_chat.side_effect = ProxyTimeout('timed out')
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The model took too long to answer. Please try again.')
        self.assertContains(response, 'What is the capital of France?</textarea>')
        self.assertFalse(ChatSession.objects.exists())

    def test_get_is_not_allowed(self, send_chat):
        self.assertEqual(self.client.get('/chat/new/').status_code, 405)

    def test_anonymous_user_is_redirected_to_login(self, send_chat):
        self.client.logout()
        response = self.post()
        self.assertRedirects(response, '/accounts/login/?next=/chat/new/', fetch_redirect_response=False)
        send_chat.assert_not_called()
