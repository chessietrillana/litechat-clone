import importlib

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from catalog.models import LLMModel, Provider, Tier
from proxy.client import ADAPTERS


def make_model(proxy_model_id, **kwargs):
    fields = {
        'display_name': f'Test {proxy_model_id}',
        'provider': Provider.OPENAI,
        'tier': Tier.STANDARD,
        **kwargs,
    }
    return LLMModel.objects.create(proxy_model_id=proxy_model_id, **fields)


class LLMModelTests(TestCase):
    # The table may already hold seed rows, so tests only look at their own rows.

    def test_str_is_display_name(self):
        self.assertEqual(str(make_model('t-str', display_name='Nice Name')), 'Nice Name')

    def test_default_order_is_tier_then_name(self):
        make_model('t-3', display_name='B', tier=Tier.PREMIUM)
        make_model('t-1b', display_name='Z', tier=Tier.VALUE)
        make_model('t-1a', display_name='A', tier=Tier.VALUE)
        make_model('t-2', display_name='M', tier=Tier.STANDARD)
        ids = list(LLMModel.objects.filter(proxy_model_id__startswith='t-')
                   .values_list('proxy_model_id', flat=True))
        self.assertEqual(ids, ['t-1a', 't-1b', 't-2', 't-3'])

    def test_active_leaves_out_inactive(self):
        on = make_model('t-on')
        off = make_model('t-off', is_active=False)
        active = LLMModel.objects.active()
        self.assertIn(on, active)
        self.assertNotIn(off, active)

    def test_proxy_model_id_is_unique(self):
        make_model('t-dup')
        with self.assertRaises(IntegrityError):
            make_model('t-dup')

    def test_providers_match_proxy_interfaces(self):
        self.assertEqual(set(Provider.values), set(ADAPTERS))
        self.assertEqual(set(Provider.values), set(settings.PROXY_KEYS))


class LLMModelAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', password='correct-horse-42')
        self.client.force_login(self.admin)
        self.model = make_model('t-admin')

    def test_list_page_loads(self):
        response = self.client.get('/admin/catalog/llmmodel/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test t-admin')

    def run_action(self, action):
        return self.client.post('/admin/catalog/llmmodel/', {
            'action': action,
            '_selected_action': [self.model.pk],
        })

    def test_turn_off_and_on_actions(self):
        self.run_action('turn_off')
        self.model.refresh_from_db()
        self.assertFalse(self.model.is_active)
        self.run_action('turn_on')
        self.model.refresh_from_db()
        self.assertTrue(self.model.is_active)

    def test_delete_is_not_allowed(self):
        response = self.client.get(f'/admin/catalog/llmmodel/{self.model.pk}/delete/')
        self.assertEqual(response.status_code, 403)
        response = self.client.get('/admin/catalog/llmmodel/')
        self.assertNotContains(response, 'delete_selected')
        response = self.client.get(f'/admin/catalog/llmmodel/{self.model.pk}/change/')
        self.assertNotContains(response, 'deletelink')


class SeedTests(TestCase):
    SEED = {
        'gemini-3.8-flash': ('Gemini 3.8 Flash', Provider.GOOGLE, Tier.VALUE),
        'claude-haiku-4-5-20251001': ('Claude Haiku 4.5', Provider.ANTHROPIC, Tier.STANDARD),
        'gpt-5.6-luna': ('GPT-5.6 Luna', Provider.OPENAI, Tier.PREMIUM),
    }

    def seed_rows(self):
        return LLMModel.objects.filter(proxy_model_id__in=self.SEED)

    def test_seed_rows_exist_after_migrations(self):
        self.assertEqual(self.seed_rows().count(), 3)
        for row in self.seed_rows():
            with self.subTest(row.proxy_model_id):
                self.assertEqual((row.display_name, row.provider, row.tier), self.SEED[row.proxy_model_id])
                self.assertTrue(row.is_active)

    def test_seeding_again_changes_nothing(self):
        seed = importlib.import_module('catalog.migrations.0002_seed_proxy_models')
        LLMModel.objects.filter(proxy_model_id='gpt-5.6-luna').update(
            display_name='Renamed by admin', is_active=False
        )
        seed.seed_models(django_apps, None)
        self.assertEqual(self.seed_rows().count(), 3)
        row = LLMModel.objects.get(proxy_model_id='gpt-5.6-luna')
        self.assertEqual(row.display_name, 'Renamed by admin')
        self.assertFalse(row.is_active)


class ModelsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='correct-horse-42')

    def get_page(self):
        self.client.force_login(self.user)
        return self.client.get('/models/')

    def test_visitor_is_sent_to_login(self):
        response = self.client.get('/models/')
        self.assertRedirects(response, '/accounts/login/?next=/models/')

    def test_shows_seed_models_with_provider_and_tier_in_tier_order(self):
        response = self.get_page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<td>Gemini 3.8 Flash</td>', html=True)
        self.assertContains(response, '<td>Google</td>', html=True)
        self.assertContains(response, 'Value')
        self.assertContains(response, '<td>Anthropic</td>', html=True)
        self.assertContains(response, 'Standard')
        self.assertContains(response, '<td>OpenAI</td>', html=True)
        self.assertContains(response, 'Premium')
        html = response.content.decode()
        positions = [html.index(name) for name in ('Gemini 3.8 Flash', 'Claude Haiku 4.5', 'GPT-5.6 Luna')]
        self.assertEqual(positions, sorted(positions))

    def test_turned_off_model_is_hidden(self):
        LLMModel.objects.filter(proxy_model_id='gpt-5.6-luna').update(is_active=False)
        response = self.get_page()
        self.assertNotContains(response, 'GPT-5.6 Luna')
        self.assertContains(response, 'Gemini 3.8 Flash')

    def test_no_active_models_shows_message(self):
        LLMModel.objects.update(is_active=False)
        response = self.get_page()
        self.assertContains(response, 'No models are available right now.')
        self.assertNotContains(response, '<table')

    def test_nav_link_only_when_logged_in(self):
        response = self.get_page()
        self.assertContains(response, '<a href="/models/">Models</a>', html=True)
        self.client.logout()
        response = self.client.get('/accounts/login/')
        self.assertNotContains(response, 'href="/models/"')

    def test_home_links_to_models(self):
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, 'href="/models/"')
