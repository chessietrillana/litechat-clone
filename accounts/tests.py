from django.contrib.auth.models import User
from django.test import TestCase

PASSWORD = 'correct-horse-42'


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password=PASSWORD)

    def assertLoggedIn(self):
        self.assertIn('_auth_user_id', self.client.session)

    def assertLoggedOut(self):
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_page_shows_form(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_good_login_redirects_home(self):
        response = self.client.post('/accounts/login/', {'username': 'alice', 'password': PASSWORD})
        self.assertRedirects(response, '/')
        self.assertLoggedIn()

    def test_bad_password_shows_error(self):
        response = self.client.post('/accounts/login/', {'username': 'alice', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertLoggedOut()

    def test_anonymous_home_redirects_to_login_page(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/accounts/login/?next=/')

    def test_login_respects_next(self):
        response = self.client.post(
            '/accounts/login/?next=/', {'username': 'alice', 'password': PASSWORD, 'next': '/'}
        )
        self.assertRedirects(response, '/')

    def test_logged_in_user_is_sent_home_from_login_page(self):
        self.client.force_login(self.user)
        response = self.client.get('/accounts/login/')
        self.assertRedirects(response, '/')

    def test_logout_by_post_logs_out(self):
        self.client.force_login(self.user)
        response = self.client.post('/accounts/logout/')
        self.assertRedirects(response, '/accounts/login/')
        self.assertLoggedOut()

    def test_logout_by_get_is_refused(self):
        self.client.force_login(self.user)
        response = self.client.get('/accounts/logout/')
        self.assertEqual(response.status_code, 405)
        self.assertLoggedIn()

    def test_nav_shows_logout_button_when_logged_in(self):
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'Log out')

    def test_nav_shows_login_link_to_visitors(self):
        response = self.client.get('/accounts/login/')
        self.assertContains(response, 'href="/accounts/login/"')
        self.assertNotContains(response, 'Log out')
