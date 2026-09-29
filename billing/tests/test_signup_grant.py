import importlib

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase, override_settings

from billing.models import BillingAccount, LedgerEntry

THOUSAND_CREDITS = 1_000_000_000  # µc


class SignupGrantTests(TestCase):
    def assert_has_signup_account(self, user, micro=THOUSAND_CREDITS):
        accounts = BillingAccount.objects.filter(owner=user)
        self.assertEqual(accounts.count(), 1)
        account = accounts.get()
        self.assertEqual(account.kind, BillingAccount.Kind.PERSONAL)
        self.assertEqual(account.balance_micro(), micro)
        entry = account.entries.get()
        self.assertEqual(entry.kind, LedgerEntry.Kind.SIGNUP_GRANT)
        self.assertIsNone(entry.created_by)

    def test_create_user(self):
        self.assert_has_signup_account(User.objects.create_user('alice', password='correct-horse-42'))

    def test_signup_page(self):
        self.client.post('/accounts/signup/', {
            'username': 'bob', 'password1': 'correct-horse-42', 'password2': 'correct-horse-42',
        })
        self.assert_has_signup_account(User.objects.get(username='bob'))

    def test_create_superuser(self):
        self.assert_has_signup_account(User.objects.create_superuser('boss', password='correct-horse-42'))

    def test_saving_again_adds_nothing(self):
        user = User.objects.create_user('alice', password='correct-horse-42')
        user.first_name = 'Alice'
        user.save()
        self.assert_has_signup_account(user)

    @override_settings(BILLING_SIGNUP_GRANT_CREDITS=5)
    def test_grant_amount_is_a_setting(self):
        self.assert_has_signup_account(User.objects.create_user('alice', password='x-correct-horse-42'), 5_000_000)

    def test_user_with_ledger_entries_cannot_be_deleted(self):
        user = User.objects.create_user('alice', password='correct-horse-42')
        with self.assertRaises(ProtectedError):
            user.delete()
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assert_has_signup_account(user)


class BackfillTests(TestCase):
    def setUp(self):
        self.backfill = importlib.import_module('billing.migrations.0004_backfill_personal_accounts').backfill

    def test_backfill_gives_old_users_an_account_once(self):
        # bulk_create skips signals, like users made before billing existed.
        User.objects.bulk_create([User(username='old')])
        old = User.objects.get(username='old')
        self.assertFalse(BillingAccount.objects.filter(owner=old).exists())
        new = User.objects.create_user('new', password='correct-horse-42')

        self.backfill(django_apps, None)
        self.backfill(django_apps, None)

        for user in (old, new):
            with self.subTest(user=user.username):
                account = BillingAccount.objects.get(owner=user)
                self.assertEqual(account.balance_micro(), THOUSAND_CREDITS)
                self.assertEqual(account.entries.count(), 1)
