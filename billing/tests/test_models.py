from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from billing.models import BillingAccount, LedgerEntry

PERSONAL = BillingAccount.Kind.PERSONAL
SHARED = BillingAccount.Kind.SHARED


def personal_account(user):
    # Later steps create personal accounts automatically; reuse one if it exists.
    account, _ = BillingAccount.objects.get_or_create(kind=PERSONAL, owner=user)
    return account


def add_entry(account, micro, kind=LedgerEntry.Kind.ADMIN_GRANT):
    return LedgerEntry.objects.create(account=account, amount_micro=micro, kind=kind)


class ConstraintTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='correct-horse-42')

    def assert_rejected(self, **fields):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BillingAccount.objects.create(**fields)

    def test_personal_needs_owner(self):
        self.assert_rejected(kind=PERSONAL)

    def test_shared_has_no_owner(self):
        self.assert_rejected(kind=SHARED, name='Team', owner=self.alice)

    def test_shared_needs_name(self):
        self.assert_rejected(kind=SHARED, name='')

    def test_one_personal_account_per_user(self):
        personal_account(self.alice)
        self.assert_rejected(kind=PERSONAL, owner=self.alice)

    def test_many_shared_accounts_are_fine(self):
        BillingAccount.objects.create(kind=SHARED, name='A')
        BillingAccount.objects.create(kind=SHARED, name='B')


class ForUserTests(TestCase):
    def test_personal_plus_shared_memberships_only(self):
        alice = User.objects.create_user('alice', password='correct-horse-42')
        bob = User.objects.create_user('bob', password='correct-horse-42')
        alice_personal = personal_account(alice)
        bob_personal = personal_account(bob)
        team = BillingAccount.objects.create(kind=SHARED, name='Team')
        team.members.add(alice, bob)
        other = BillingAccount.objects.create(kind=SHARED, name='Other')
        other.members.add(bob)

        self.assertEqual(set(BillingAccount.objects.for_user(alice)), {alice_personal, team})
        self.assertEqual(set(BillingAccount.objects.for_user(bob)), {bob_personal, team, other})


class BalanceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='correct-horse-42')
        self.team = BillingAccount.objects.create(kind=SHARED, name='Team')

    def test_no_entries_is_zero(self):
        self.assertEqual(self.team.balance_micro(), 0)
        self.assertEqual(BillingAccount.objects.with_balance().get(pk=self.team.pk).balance, 0)

    def test_balance_is_sum_of_entries(self):
        add_entry(self.team, 1_000_000_000)
        add_entry(self.team, 250_500_000)
        add_entry(self.team, -183_000)  # stands in for a plan-7 charge
        self.assertEqual(self.team.balance_micro(), 1_250_317_000)

    def test_with_balance_matches_and_is_not_multiplied_by_members(self):
        bob = User.objects.create_user('bob', password='correct-horse-42')
        self.team.members.add(self.alice, bob)
        add_entry(self.team, 5_000_000)
        add_entry(self.team, 7_000_000)
        row = BillingAccount.objects.for_user(self.alice).with_balance().get(pk=self.team.pk)
        self.assertEqual(row.balance, 12_000_000)
        self.assertEqual(row.balance, self.team.balance_micro())


class StrTests(TestCase):
    def test_str(self):
        alice = User.objects.create_user('alice', password='correct-horse-42')
        self.assertEqual(str(personal_account(alice)), 'alice (personal)')
        self.assertEqual(str(BillingAccount.objects.create(kind=SHARED, name='Team')), 'Team')
        entry = add_entry(personal_account(alice), 250_500_000)
        self.assertEqual(str(entry), 'Admin grant 250.5 credits to alice (personal)')
