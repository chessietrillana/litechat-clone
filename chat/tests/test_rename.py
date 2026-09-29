from django.test import TestCase

from chat.tests.helpers import make_session, make_user


def rename_url(session):
    return f'/chat/{session.pk}/rename/'


class RenameChatTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.client.force_login(self.alice)
        self.session = make_session(self.alice, title='Capitals')

    def assert_title(self, session, title):
        session.refresh_from_db()
        self.assertEqual(session.title, title)

    def test_login_needed(self):
        self.client.logout()
        url = rename_url(self.session)
        response = self.client.get(url)
        self.assertRedirects(response, f'/accounts/login/?next={url}', fetch_redirect_response=False)
        self.client.post(url, {'title': 'Hacked'})
        self.assert_title(self.session, 'Capitals')

    def test_sidebar_has_rename_link(self):
        response = self.client.get('/')
        self.assertContains(response, f'<a href="{rename_url(self.session)}">Rename</a>', html=True)

    def test_get_shows_box_with_current_title(self):
        response = self.client.get(rename_url(self.session))
        self.assertContains(response, 'value="Capitals"')
        self.assertContains(response, 'maxlength="100"')
        self.assertContains(response, f'action="{rename_url(self.session)}"')
        self.assertContains(response, f'<a href="/chat/{self.session.pk}/">Cancel</a>', html=True)

    def test_post_saves_and_goes_back_to_the_chat(self):
        response = self.client.post(rename_url(self.session), {'title': 'Trip ideas'}, follow=True)
        self.assertRedirects(response, f'/chat/{self.session.pk}/')
        self.assertContains(response, 'Chat renamed.')
        self.assertContains(response, '<h1 class="chat-title">Trip ideas</h1>', html=True)
        self.assertContains(response, 'aria-label="Options for Trip ideas"')
        self.assertNotContains(response, 'Capitals')
        self.assert_title(self.session, 'Trip ideas')

    def test_spaces_around_are_removed(self):
        self.client.post(rename_url(self.session), {'title': '  Trip ideas \t'})
        self.assert_title(self.session, 'Trip ideas')

    def test_blank_is_refused(self):
        for blank in ('', '   '):
            with self.subTest(title=blank):
                response = self.client.post(rename_url(self.session), {'title': blank})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Enter a title.')
                self.assert_title(self.session, 'Capitals')

    def test_max_length(self):
        response = self.client.post(rename_url(self.session), {'title': 'x' * 101})
        self.assertContains(response, 'at most 100 characters')
        self.assertContains(response, 'value="' + 'x' * 101 + '"')  # The typed text is kept.
        self.assertContains(response, '<h1>Rename "Capitals"</h1>', html=True)
        self.assert_title(self.session, 'Capitals')
        self.client.post(rename_url(self.session), {'title': 'y' * 100})
        self.assert_title(self.session, 'y' * 100)

    def test_html_in_title_is_shown_as_text(self):
        self.client.post(rename_url(self.session), {'title': '<b>bold</b>'})
        response = self.client.get(f'/chat/{self.session.pk}/')
        self.assertNotContains(response, '<b>bold</b>')
        self.assertContains(response, '&lt;b&gt;bold&lt;/b&gt;')

    def test_rename_keeps_place_in_sidebar(self):
        updated_at = self.session.updated_at
        self.client.post(rename_url(self.session), {'title': 'Trip ideas'})
        self.session.refresh_from_db()
        self.assertEqual(self.session.updated_at, updated_at)

    def test_other_hidden_and_missing_chats_are_404(self):
        bobs = make_session(make_user('bob'), title='Bob chat')
        gone = make_session(self.alice, title='Gone')
        gone.hide()
        for session, title in ((bobs, 'Bob chat'), (gone, 'Gone')):
            with self.subTest(title=title):
                self.assertEqual(self.client.get(rename_url(session)).status_code, 404)
                response = self.client.post(rename_url(session), {'title': 'Hacked'})
                self.assertEqual(response.status_code, 404)
                self.assert_title(session, title)
        self.assertEqual(self.client.get('/chat/9999/rename/').status_code, 404)

    def test_other_methods_are_not_allowed(self):
        self.assertEqual(self.client.put(rename_url(self.session)).status_code, 405)
