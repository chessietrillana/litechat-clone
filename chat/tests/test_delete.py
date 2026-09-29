from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from billing.models import LedgerEntry
from chat.models import ChatSession
from chat.services import start_session
from chat.tests.helpers import make_session, make_user, personal_account, reply, seeded_model


def delete_url(session):
    return f'/chat/{session.pk}/delete/'


class DeleteChatTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.client.force_login(self.alice)
        self.session = make_session(self.alice, title='Trip ideas', turns=1)

    def assert_visible(self, session):
        session.refresh_from_db()
        self.assertIsNone(session.hidden_at)

    def test_login_needed(self):
        self.client.logout()
        url = delete_url(self.session)
        response = self.client.get(url)
        self.assertRedirects(response, f'/accounts/login/?next={url}', fetch_redirect_response=False)
        self.client.post(url)
        self.assert_visible(self.session)

    def test_sidebar_has_delete_link_and_menu_label(self):
        other = make_session(self.alice, title='Capitals')
        response = self.client.get('/')
        self.assertContains(response, f'<a href="{delete_url(self.session)}">Delete</a>', html=True)
        self.assertContains(response, f'<a href="{delete_url(other)}">Delete</a>', html=True)
        self.assertContains(response, 'aria-label="Options for Trip ideas"')

    def test_get_asks_to_confirm_and_hides_nothing(self):
        response = self.client.get(delete_url(self.session))
        self.assertContains(response, '<h1>Delete "Trip ideas"?</h1>', html=True)
        self.assertContains(response, 'Its charges stay on the')
        self.assertContains(response, f'action="{delete_url(self.session)}"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, f'<a href="/chat/{self.session.pk}/">Cancel</a>', html=True)
        self.assert_visible(self.session)

    def test_post_hides_goes_home_and_says_so(self):
        response = self.client.post(delete_url(self.session), follow=True)
        self.assertRedirects(response, '/')
        self.assertContains(response, 'Deleted &quot;Trip ideas&quot;.')
        self.assertNotContains(response, f'href="/chat/{self.session.pk}/"')
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.hidden_at)
        self.assertEqual(self.client.get(f'/chat/{self.session.pk}/').status_code, 404)

    def test_deleting_another_chat_than_the_open_one_also_goes_home(self):
        other = make_session(self.alice, title='Capitals')
        response = self.client.post(delete_url(other))
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assert_visible(self.session)

    def test_other_users_chat_is_404_and_stays(self):
        bobs = make_session(make_user('bob'), title='Bob chat')
        self.assertEqual(self.client.get(delete_url(bobs)).status_code, 404)
        self.assertEqual(self.client.post(delete_url(bobs)).status_code, 404)
        self.assert_visible(bobs)

    def test_hidden_or_missing_chat_is_404(self):
        self.client.post(delete_url(self.session))
        self.assertEqual(self.client.get(delete_url(self.session)).status_code, 404)
        self.assertEqual(self.client.post(delete_url(self.session)).status_code, 404)
        self.assertEqual(self.client.get('/chat/9999/delete/').status_code, 404)

    def test_other_methods_are_not_allowed(self):
        self.assertEqual(self.client.put(delete_url(self.session)).status_code, 405)
        self.assert_visible(self.session)

    def test_query_count_does_not_grow_with_the_sidebar(self):
        one = self.count_queries()
        for n in range(10):
            make_session(self.alice, title=f'chat {n}')
        self.assertEqual(self.count_queries(), one)

    def count_queries(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(delete_url(self.session)).status_code, 200)
        return len(queries)


@mock.patch('chat.services.send_chat')
class DeleteKeepsChargesTests(TestCase):
    def test_charges_and_balance_stay(self, send_chat):
        send_chat.return_value = reply(input_tokens=183, output_tokens=12)
        alice = make_user('alice')
        account = personal_account(alice)
        session = start_session(alice, seeded_model(), account, 'Hi')
        charges = list(LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CHARGE))
        balance = account.balance_micro()

        self.client.force_login(alice)
        self.client.post(delete_url(session))

        self.assertEqual(list(LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CHARGE)), charges)
        self.assertEqual(account.balance_micro(), balance)
        self.assertEqual(ChatSession.objects.get(pk=session.pk).messages.count(), 2)
