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


@mock.patch('chat.services.send_chat')
class SessionPageTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.client.force_login(self.alice)
        self.session = make_session(self.alice, title='Capitals', turns=2)
        self.url = f'/chat/{self.session.pk}/'

    def test_owner_sees_messages_in_order_as_bubbles(self, send_chat):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        positions = [content.index(t) for t in ['question 1', 'answer 1', 'question 2', 'answer 2']]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(content.count('class="bubble bubble-user"'), 2)
        self.assertEqual(content.count('class="bubble bubble-assistant"'), 2)
        self.assertContains(response, 'Gemini 3.8 Flash (Value)')
        self.assertContains(response, 'billed to alice (personal)')

    def test_other_user_gets_404(self, send_chat):
        self.client.force_login(make_user('bob'))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'message': 'Hi'}).status_code, 404)
        send_chat.assert_not_called()

    def test_anonymous_user_is_redirected_to_login(self, send_chat):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f'/accounts/login/?next={self.url}', fetch_redirect_response=False)

    def test_missing_session_is_404(self, send_chat):
        self.assertEqual(self.client.get('/chat/9999/').status_code, 404)

    def test_send_saves_turn_and_redirects(self, send_chat):
        send_chat.return_value = reply(text='answer 3')
        response = self.client.post(self.url, {'message': 'question 3'})
        self.assertRedirects(response, self.url)
        self.assertEqual(len(send_chat.call_args.args[2]), 5)
        self.assertEqual(self.session.messages.count(), 6)
        self.assertContains(self.client.get(self.url), 'answer 3')

    def test_proxy_failure_shows_error_keeps_text_saves_nothing(self, send_chat):
        send_chat.side_effect = ProxyTimeout('timed out')
        response = self.client.post(self.url, {'message': 'question 3'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The model took too long to answer. Please try again.')
        self.assertContains(response, 'question 3</textarea>')
        self.assertEqual(self.session.messages.count(), 4)

    def test_turned_off_model_shows_message_and_old_messages(self, send_chat):
        self.session.llm_model.is_active = False
        self.session.llm_model.save()
        response = self.client.post(self.url, {'message': 'question 3'})
        self.assertContains(response, 'This model has been turned off.')
        self.assertContains(response, 'answer 2')
        send_chat.assert_not_called()

    def test_blank_message_is_refused(self, send_chat):
        response = self.client.post(self.url, {'message': '  '})
        self.assertContains(response, 'Type a message first.')
        send_chat.assert_not_called()

    def test_cut_off_reply_shows_note(self, send_chat):
        send_chat.return_value = reply(text='A long answer', finish_reason='length')
        self.client.post(self.url, {'message': 'question 3'})
        response = self.client.get(self.url)
        self.assertContains(response, 'This reply was cut off at the length limit.', count=1)

    def test_html_in_messages_is_shown_as_text(self, send_chat):
        send_chat.return_value = reply(text='<b>bold</b>')
        self.client.post(self.url, {'message': '<script>alert(1)</script>'})
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;b&gt;bold&lt;/b&gt;')

    def test_model_and_account_cannot_be_changed(self, send_chat):
        response = self.client.get(self.url)
        self.assertNotContains(response, '<select')
        send_chat.return_value = reply()
        other = seeded_model('gpt-5.6-luna')
        self.client.post(self.url, {'message': 'question 3', 'llm_model': other.pk})
        self.session.refresh_from_db()
        self.assertEqual(self.session.llm_model.proxy_model_id, 'gemini-3.8-flash')
        self.assertEqual(send_chat.call_args.args[1], 'gemini-3.8-flash')

    def test_line_breaks_are_kept(self, send_chat):
        send_chat.return_value = reply(text='line one\nline two')
        self.client.post(self.url, {'message': 'question 3'})
        self.assertContains(self.client.get(self.url), 'line one\nline two')
