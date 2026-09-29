from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from billing.models import BillingAccount, LedgerEntry


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


class HomeBillingAccountsTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='correct-horse-42')
        self.bob = User.objects.create_user('bob', password='correct-horse-42')

    def get_home(self, user):
        self.client.force_login(user)
        return self.client.get('/')

    def test_new_user_sees_personal_account_with_signup_credits(self):
        response = self.get_home(self.alice)
        self.assertContains(response, 'Your billing accounts')
        self.assertContains(response, '<li>alice (personal): 1,000 credits</li>', html=True)

    def test_member_sees_shared_account_but_not_others(self):
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Study group')
        team.members.add(self.alice)
        LedgerEntry.objects.create(account=team, amount_micro=500_000_000, kind=LedgerEntry.Kind.ADMIN_GRANT)
        BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Secret club')

        response = self.get_home(self.alice)
        self.assertContains(response, '<li>Study group: 500 credits</li>', html=True)
        self.assertNotContains(response, 'Secret club')
        self.assertNotContains(response, 'bob (personal)')

        response = self.get_home(self.bob)
        self.assertContains(response, '<li>bob (personal): 1,000 credits</li>', html=True)
        self.assertNotContains(response, 'Study group')
        self.assertNotContains(response, 'alice (personal)')
