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
