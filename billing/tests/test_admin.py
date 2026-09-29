from django.contrib.auth.models import User
from django.test import TestCase

from billing.models import BillingAccount, LedgerEntry

ACCOUNTS = '/admin/billing/billingaccount/'
ENTRIES = '/admin/billing/ledgerentry/'


class BillingAdminTestCase(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser('boss', password='correct-horse-42')
        self.alice = User.objects.create_user('alice', password='correct-horse-42')
        self.bob = User.objects.create_user('bob', password='correct-horse-42')
        self.alice_personal = BillingAccount.objects.get(owner=self.alice)
        self.client.force_login(self.boss)


class BillingAccountAdminTests(BillingAdminTestCase):
    def test_list_shows_balances(self):
        response = self.client.get(ACCOUNTS)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alice (personal)')
        self.assertContains(response, '1,000')

    def test_add_shared_account_with_members(self):
        response = self.client.post(f'{ACCOUNTS}add/', {
            'name': 'Study group',
            'members': [self.alice.pk, self.bob.pk],
            'entries-TOTAL_FORMS': '0', 'entries-INITIAL_FORMS': '0',
        })
        self.assertEqual(response.status_code, 302)
        team = BillingAccount.objects.get(name='Study group')
        self.assertEqual(team.kind, BillingAccount.Kind.SHARED)
        self.assertIsNone(team.owner)
        self.assertEqual(set(team.members.all()), {self.alice, self.bob})

    def test_shared_account_needs_name(self):
        response = self.client.post(f'{ACCOUNTS}add/', {
            'name': '  ', 'entries-TOTAL_FORMS': '0', 'entries-INITIAL_FORMS': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A shared account needs a name.')
        self.assertFalse(BillingAccount.objects.filter(kind=BillingAccount.Kind.SHARED).exists())

    def test_personal_account_page_has_no_members_and_is_locked(self):
        url = f'{ACCOUNTS}{self.alice_personal.pk}/change/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="members"')
        self.assertNotContains(response, 'name="owner"')
        self.assertNotContains(response, 'name="kind"')
        self.assertContains(response, 'Grant credits')
        self.assertContains(response, 'Sign-up credits')  # read-only ledger inline

    def test_accounts_cannot_be_deleted(self):
        response = self.client.get(f'{ACCOUNTS}{self.alice_personal.pk}/delete/')
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(self.client.get(ACCOUNTS), 'delete_selected')
        self.assertNotContains(self.client.get(f'{ACCOUNTS}{self.alice_personal.pk}/change/'), 'deletelink')


class GrantAdminTests(BillingAdminTestCase):
    def grant(self, amount, account=None):
        return self.client.post(f'{ENTRIES}add/', {
            'account': (account or self.alice_personal).pk,
            'amount_credits': amount,
            'note': 'Test grant',
        })

    def test_grant_form_prefills_account(self):
        response = self.client.get(f'{ENTRIES}add/?account={self.alice_personal.pk}')
        self.assertContains(response, 'Grant credits')
        self.assertEqual(response.context['adminform'].form.initial['account'], str(self.alice_personal.pk))

    def test_grant_adds_admin_entry(self):
        before = self.alice_personal.balance_micro()
        response = self.grant('250.5')
        self.assertEqual(response.status_code, 302)
        entry = LedgerEntry.objects.get(kind=LedgerEntry.Kind.ADMIN_GRANT)
        self.assertEqual(entry.amount_micro, 250_500_000)
        self.assertEqual(entry.created_by, self.boss)
        self.assertEqual(entry.note, 'Test grant')
        self.assertEqual(self.alice_personal.balance_micro(), before + 250_500_000)

    def test_bad_amounts_are_refused(self):
        for amount in ('0', '-5', '0.0000001', 'abc'):
            with self.subTest(amount=amount):
                response = self.grant(amount)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'errorlist')
        self.assertFalse(LedgerEntry.objects.filter(kind=LedgerEntry.Kind.ADMIN_GRANT).exists())

    def test_entries_are_read_only(self):
        entry = self.alice_personal.entries.get()
        url = f'{ENTRIES}{entry.pk}/change/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="amount_credits"')
        self.assertNotContains(response, 'name="_save"')
        response = self.client.post(url, {'note': 'edited'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(f'{ENTRIES}{entry.pk}/delete/').status_code, 403)
        entry.refresh_from_db()
        self.assertEqual(entry.note, 'Sign-up credits')

    def test_non_staff_cannot_grant(self):
        self.client.force_login(self.alice)
        response = self.client.get(f'{ENTRIES}add/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])
