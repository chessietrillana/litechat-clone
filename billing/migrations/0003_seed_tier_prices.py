"""Seed placeholder tier prices (study NOTE Q6): credits per 1K tokens.

get_or_create by tier: running it again never overwrites a price an admin
changed. Undoing the migration deletes nothing.
"""
from decimal import Decimal

from django.db import migrations

# (tier: 1 Value / 2 Standard / 3 Premium, credits per 1K tokens)
SEED_PRICES = [
    (1, Decimal('1')),
    (2, Decimal('3')),
    (3, Decimal('10')),
]


def seed_prices(apps, schema_editor):
    TierPrice = apps.get_model('billing', 'TierPrice')
    for tier, price in SEED_PRICES:
        TierPrice.objects.get_or_create(tier=tier, defaults={'price_per_1k_tokens': price})


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_tierprice'),
    ]

    operations = [
        migrations.RunPython(seed_prices, migrations.RunPython.noop),
    ]
