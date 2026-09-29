from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase


class ProjectSetupTests(TestCase):
    def test_admin_login_page_loads(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)

    def test_proxy_keys_has_one_entry_per_interface(self):
        # Only the names are checked. Key values are never read in tests.
        self.assertEqual(set(settings.PROXY_KEYS), {'openai', 'anthropic', 'google'})


class HomePageTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/accounts/login/?next=/', fetch_redirect_response=False)

    def test_logged_in_user_sees_their_username(self):
        user = User.objects.create_user('alice', password='correct-horse-42')
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello, alice.')
