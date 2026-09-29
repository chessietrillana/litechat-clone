import logging

from django.conf import settings
from django.test import TestCase


class ProjectSetupTests(TestCase):
    def test_admin_login_page_loads(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)

    def test_proxy_keys_has_one_entry_per_interface(self):
        # Only the names are checked. Key values are never read in tests.
        self.assertEqual(set(settings.PROXY_KEYS), {'openai', 'anthropic', 'google'})


class LoggingTests(TestCase):
    def test_proxy_logger_shows_info_on_the_console(self):
        logger = logging.getLogger('proxy')
        self.assertEqual(logger.level, logging.INFO)
        self.assertTrue(any(isinstance(h, logging.StreamHandler) for h in logger.handlers))
