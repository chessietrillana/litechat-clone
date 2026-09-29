"""Seed the three models the proxy offers (study NOTEs Q1-Q3).

get_or_create by proxy_model_id: running it again never duplicates rows
and never undoes changes an admin made. Undoing the migration deletes nothing.
"""
from django.db import migrations

SEED_MODELS = [
    # (proxy_model_id, display_name, provider, tier: 1 Value / 2 Standard / 3 Premium)
    ('gemini-3.8-flash', 'Gemini 3.8 Flash', 'google', 1),
    ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5', 'anthropic', 2),
    ('gpt-5.6-luna', 'GPT-5.6 Luna', 'openai', 3),
]


def seed_models(apps, schema_editor):
    LLMModel = apps.get_model('catalog', 'LLMModel')
    for proxy_model_id, display_name, provider, tier in SEED_MODELS:
        LLMModel.objects.get_or_create(
            proxy_model_id=proxy_model_id,
            defaults={
                'display_name': display_name,
                'provider': provider,
                'tier': tier,
                'is_active': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_models, migrations.RunPython.noop),
    ]
