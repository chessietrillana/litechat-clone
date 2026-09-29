import importlib
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.test import TestCase

from billing.models import TierPrice
from catalog.models import Tier


class TierPriceTests(TestCase):
    def test_seeded_prices(self):
        prices = {p.tier: p.price_per_1k_tokens for p in TierPrice.objects.all()}
        self.assertEqual(prices, {
            Tier.VALUE: Decimal('1'),
            Tier.STANDARD: Decimal('3'),
            Tier.PREMIUM: Decimal('10'),
        })

    def test_micro_per_token(self):
        per_token = {p.tier: p.micro_per_token for p in TierPrice.objects.all()}
        self.assertEqual(per_token, {Tier.VALUE: 1_000, Tier.STANDARD: 3_000, Tier.PREMIUM: 10_000})
        for price, micro in ((Decimal('1.5'), 1_500), (Decimal('0.001'), 1), (Decimal('12.345'), 12_345)):
            with self.subTest(price=price):
                self.assertEqual(TierPrice(tier=Tier.VALUE, price_per_1k_tokens=price).micro_per_token, micro)

    def test_str(self):
        self.assertEqual(str(TierPrice.objects.get(tier=Tier.PREMIUM)), 'Premium: 10 credits per 1K tokens')

    def test_seeding_again_keeps_admin_changes(self):
        seed = importlib.import_module('billing.migrations.0003_seed_tier_prices')
        TierPrice.objects.filter(tier=Tier.VALUE).update(price_per_1k_tokens=Decimal('2.5'))
        seed.seed_prices(django_apps, None)
        self.assertEqual(TierPrice.objects.count(), 3)
        self.assertEqual(TierPrice.objects.get(tier=Tier.VALUE).price_per_1k_tokens, Decimal('2.5'))


class TierPriceAdminTests(TestCase):
    URL = '/admin/billing/tierprice/'

    def setUp(self):
        self.client.force_login(User.objects.create_superuser('boss', password='correct-horse-42'))

    def test_list_loads_without_add_or_delete(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Premium')
        self.assertNotContains(response, f'{self.URL}add/')
        self.assertNotContains(response, 'delete_selected')
        self.assertEqual(self.client.get(f'{self.URL}add/').status_code, 403)
        value = TierPrice.objects.get(tier=Tier.VALUE)
        self.assertEqual(self.client.get(f'{self.URL}{value.pk}/delete/').status_code, 403)

    def test_edit_price_in_list(self):
        prices = list(TierPrice.objects.all())
        data = {
            'form-TOTAL_FORMS': str(len(prices)),
            'form-INITIAL_FORMS': str(len(prices)),
            '_save': 'Save',
        }
        for i, price in enumerate(prices):
            data[f'form-{i}-id'] = str(price.pk)
            new = '1.5' if price.tier == Tier.VALUE else str(price.price_per_1k_tokens)
            data[f'form-{i}-price_per_1k_tokens'] = new
        response = self.client.post(self.URL, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TierPrice.objects.get(tier=Tier.VALUE).price_per_1k_tokens, Decimal('1.5'))

    def test_negative_price_is_refused(self):
        value = TierPrice.objects.get(tier=Tier.VALUE)
        response = self.client.post(f'{self.URL}{value.pk}/change/', {'price_per_1k_tokens': '-1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        value.refresh_from_db()
        self.assertEqual(value.price_per_1k_tokens, Decimal('1'))
