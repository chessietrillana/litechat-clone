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


class SignUpTests(TestCase):
    def post_signup(self, username='bob', password1=PASSWORD, password2=PASSWORD):
        return self.client.post(
            '/accounts/signup/',
            {'username': username, 'password1': password1, 'password2': password2},
        )

    def test_signup_page_shows_username_and_two_passwords_only(self):
        response = self.client.get('/accounts/signup/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['form'].fields), ['username', 'password1', 'password2'])
        self.assertNotContains(response, 'name="email"')

    def test_valid_signup_creates_user_logs_in_and_redirects_home(self):
        response = self.post_signup()
        self.assertRedirects(response, '/')
        user = User.objects.get(username='bob')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_new_user_is_not_staff_or_superuser(self):
        self.post_signup()
        user = User.objects.get(username='bob')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_taken_username_is_rejected(self):
        User.objects.create_user('bob', password=PASSWORD)
        response = self.post_signup()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertEqual(User.objects.filter(username='bob').count(), 1)

    def test_mismatched_passwords_are_rejected(self):
        response = self.post_signup(password2='different-horse-43')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertFalse(User.objects.filter(username='bob').exists())

    def test_weak_password_is_rejected(self):
        response = self.post_signup(password1='12345678', password2='12345678')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertFalse(User.objects.filter(username='bob').exists())

    def test_logged_in_user_is_sent_home_from_signup_page(self):
        self.client.force_login(User.objects.create_user('bob', password=PASSWORD))
        response = self.client.get('/accounts/signup/')
        self.assertRedirects(response, '/')

    def test_login_page_links_to_signup(self):
        response = self.client.get('/accounts/login/')
        self.assertContains(response, 'href="/accounts/signup/"')
