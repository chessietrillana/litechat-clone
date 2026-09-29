from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from billing.charges import record_charge
from billing.models import BillingAccount, LedgerEntry, TierPrice
from catalog.models import Tier

ENTRIES = '/admin/billing/ledgerentry/'


class CostTests(TestCase):
    def test_cost_is_tokens_times_price(self):
        standard = TierPrice.objects.get(tier=Tier.STANDARD)
        self.assertEqual(standard.cost_micro(195), 585_000)  # 0.585 credits
        self.assertEqual(standard.cost_micro(0), 0)

    def test_free_and_tiny_prices_stay_exact(self):
        self.assertEqual(TierPrice(tier=Tier.VALUE, price_per_1k_tokens=Decimal('0')).cost_micro(500), 0)
        self.assertEqual(TierPrice(tier=Tier.VALUE, price_per_1k_tokens=Decimal('0.001')).cost_micro(183), 183)


class RecordChargeTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='correct-horse-42')
        self.account = BillingAccount.objects.get(owner=self.alice)
        self.standard = TierPrice.objects.get(tier=Tier.STANDARD)

    def test_saves_a_negative_charge_with_price_and_tokens(self):
        before = self.account.balance_micro()
        entry = record_charge(self.account, self.alice, 195, self.standard)
        entry.refresh_from_db()
        self.assertEqual(entry.kind, LedgerEntry.Kind.CHARGE)
        self.assertEqual(entry.amount_micro, -585_000)
        self.assertEqual(entry.tokens, 195)
        self.assertEqual(entry.price_per_1k_tokens, Decimal('3'))
        self.assertEqual(entry.created_by, self.alice)
        self.assertEqual(entry.note, 'Standard tier')
        self.assertEqual(self.account.balance_micro(), before - 585_000)

    def test_later_price_change_keeps_old_charge(self):
        entry = record_charge(self.account, self.alice, 1000, self.standard)
        self.standard.price_per_1k_tokens = Decimal('5')
        self.standard.save()
        entry.refresh_from_db()
        self.assertEqual(entry.price_per_1k_tokens, Decimal('3'))
        self.assertEqual(entry.amount_micro, -3_000_000)

    def test_charge_can_take_balance_below_zero(self):
        record_charge(self.account, self.alice, 1_000_000, self.standard)  # 3,000 credits
        self.assertEqual(self.account.balance_micro(), -2_000 * 1_000_000)


class ChargeConstraintTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='correct-horse-42')
        self.account = BillingAccount.objects.get(owner=self.alice)

    def assert_refused(self, **fields):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LedgerEntry.objects.create(account=self.account, **fields)

    def test_charge_needs_tokens_and_price(self):
        self.assert_refused(kind='charge', amount_micro=-1, tokens=1)
        self.assert_refused(kind='charge', amount_micro=-1, price_per_1k_tokens=Decimal('1'))

    def test_charge_cannot_add_credits(self):
        self.assert_refused(kind='charge', amount_micro=1, tokens=1, price_per_1k_tokens=Decimal('1'))

    def test_grants_have_no_tokens_or_price(self):
        self.assert_refused(kind='admin_grant', amount_micro=1, tokens=1)
        self.assert_refused(kind='admin_grant', amount_micro=1, price_per_1k_tokens=Decimal('1'))

    def test_zero_cost_charge_is_allowed(self):
        LedgerEntry.objects.create(
            account=self.account, kind='charge', amount_micro=0, tokens=10, price_per_1k_tokens=Decimal('0'),
        )


class ChargeAdminTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser('boss', password='correct-horse-42')
        self.alice = User.objects.create_user('alice', password='correct-horse-42')
        account = BillingAccount.objects.get(owner=self.alice)
        self.charge = record_charge(account, self.alice, 195, TierPrice.objects.get(tier=Tier.STANDARD))
        self.client.force_login(self.boss)

    def test_list_shows_tokens_and_price(self):
        response = self.client.get(f'{ENTRIES}?kind=charge')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Charge')
        self.assertContains(response, '-0.585')
        self.assertContains(response, '195')
        self.assertContains(response, '3.000')
        self.assertNotContains(response, 'Sign-up credits')

    def test_charge_is_read_only(self):
        url = f'{ENTRIES}{self.charge.pk}/change/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '195')
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(self.client.post(url, {'note': 'edited'}).status_code, 403)
        self.assertEqual(self.client.get(f'{ENTRIES}{self.charge.pk}/delete/').status_code, 403)

    def test_account_page_lists_the_charge(self):
        response = self.client.get(f'/admin/billing/billingaccount/{self.charge.account.pk}/change/')
        self.assertContains(response, 'Standard tier')
        self.assertContains(response, '999.415')
