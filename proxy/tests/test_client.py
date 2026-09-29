from unittest import mock

from django.test import SimpleTestCase, override_settings

from proxy.client import send_chat
from proxy.errors import (
    ProxyAuthError, ProxyBadRequestError, ProxyConfigError, ProxyError, ProxyRateLimitError,
    ProxyResponseError, ProxyTimeout, ProxyUpstreamError,
)
from proxy.tests.helpers import HELLO, MULTITURN, load_fixture
from proxy.types import ChatResult, Message

FAKE_KEYS = {
    'openai': 'fake-openai-key-1111',
    'anthropic': 'fake-anthropic-key-2222',
    'google': 'fake-google-key-3333',
}
MODELS = {
    'openai': 'gpt-5.6-luna',
    'anthropic': 'claude-haiku-4-5-20251001',
    'google': 'gemini-3.8-flash',
}
SAMPLES = {
    'openai': 'openai_multiturn.json',
    'anthropic': 'anthropic_multiturn.json',
    'google': 'google_multiturn.json',
}
BASE = 'https://proxy.example'


@override_settings(PROXY_KEYS=FAKE_KEYS, PROXY_BASE_URL=BASE,
                   PROXY_TIMEOUT_SECONDS=30, PROXY_DEFAULT_MAX_TOKENS=1024)
@mock.patch('proxy.client.transport.post_json')
class SendChatTests(SimpleTestCase):
    def send(self, interface='openai', history=MULTITURN, **kwargs):
        return send_chat(interface, MODELS.get(interface, 'm'), history, **kwargs)

    def test_each_interface_uses_its_url_and_auth_header(self, post_json):
        expected = {
            'openai': (f'{BASE}/openai/v1/chat/completions',
                       {'Authorization': 'Bearer fake-openai-key-1111'}),
            'anthropic': (f'{BASE}/anthropic/v1/messages',
                          {'x-api-key': 'fake-anthropic-key-2222', 'anthropic-version': '2023-06-01'}),
            'google': (f'{BASE}/google/v1beta/models/gemini-3.8-flash:generateContent',
                       {'x-goog-api-key': 'fake-google-key-3333'}),
        }
        for interface, (url, headers) in expected.items():
            with self.subTest(interface=interface):
                post_json.reset_mock()
                post_json.return_value = (200, load_fixture(SAMPLES[interface]))
                result = self.send(interface)
                self.assertIsInstance(result, ChatResult)
                self.assertEqual(result.text, 'You asked me to say hello in one sentence.')
                self.assertEqual((result.input_tokens, result.output_tokens), (203, 10))
                called_url, called_headers, _, _ = post_json.call_args.args
                self.assertEqual(called_url, url)
                self.assertEqual(called_headers, headers)

    def test_defaults_for_max_tokens_and_timeout(self, post_json):
        post_json.return_value = (200, load_fixture('openai_single.json'))
        self.send(history=HELLO)
        _, _, body, timeout = post_json.call_args.args
        self.assertEqual(body['max_tokens'], 1024)
        self.assertEqual(timeout, 30)

    def test_max_tokens_and_system_can_be_passed(self, post_json):
        post_json.return_value = (200, load_fixture('openai_single.json'))
        self.send(history=HELLO, max_tokens=50, system='Be brief.', timeout=5)
        _, _, body, timeout = post_json.call_args.args
        self.assertEqual(body['max_tokens'], 50)
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': 'Be brief.'})
        self.assertEqual(timeout, 5)

    def test_unknown_interface(self, post_json):
        with self.assertRaises(ProxyConfigError):
            self.send('mistral')
        post_json.assert_not_called()

    def test_empty_key_does_not_call_proxy(self, post_json):
        with override_settings(PROXY_KEYS={**FAKE_KEYS, 'anthropic': ''}):
            with self.assertRaises(ProxyConfigError):
                self.send('anthropic')
        post_json.assert_not_called()

    def test_bad_history_raises_value_error(self, post_json):
        bad_histories = {
            'empty': [],
            'ends with assistant': [Message('user', 'hi'), Message('assistant', 'hello')],
            'starts with assistant': [Message('assistant', 'hello'), Message('user', 'hi')],
            'wrong role': [Message('system', 'x'), Message('user', 'hi')],
            'empty content': [Message('user', '')],
            'content not a string': [Message('user', None)],
        }
        for name, history in bad_histories.items():
            with self.subTest(name), self.assertRaises(ValueError):
                self.send(history=history)
        post_json.assert_not_called()

    def test_status_maps_to_error(self, post_json):
        cases = {
            400: ProxyBadRequestError,
            404: ProxyBadRequestError,
            401: ProxyAuthError,
            403: ProxyAuthError,
            429: ProxyRateLimitError,
            500: ProxyUpstreamError,
            502: ProxyUpstreamError,
            503: ProxyUpstreamError,
            504: ProxyUpstreamError,
        }
        for status, error_class in cases.items():
            with self.subTest(status=status):
                post_json.return_value = (status, {'error': {'message': f'proxy said {status}'}})
                with self.assertRaises(error_class) as ctx:
                    self.send()
                self.assertEqual(ctx.exception.status, status)
                self.assertEqual(ctx.exception.detail, f'proxy said {status}')
                self.assertTrue(ctx.exception.user_message)

    def test_error_status_with_unreadable_body(self, post_json):
        post_json.return_value = (502, None)
        with self.assertRaises(ProxyUpstreamError) as ctx:
            self.send()
        self.assertEqual(ctx.exception.detail, '')

    def test_200_with_no_reply_raises_response_error(self, post_json):
        for interface in ('openai', 'anthropic', 'google'):
            with self.subTest(interface=interface):
                post_json.return_value = (200, {})
                with self.assertRaises(ProxyResponseError):
                    self.send(interface)

    def test_transport_errors_pass_through(self, post_json):
        post_json.side_effect = ProxyTimeout('no answer within 30 s')
        with self.assertRaises(ProxyTimeout):
            self.send()
        self.assertEqual(post_json.call_count, 1)

    def test_keys_and_message_text_never_logged_or_in_errors(self, post_json):
        secret_text = 'my secret question'
        history = [Message('user', secret_text)]
        for interface in ('openai', 'anthropic', 'google'):
            outcomes = [
                (200, load_fixture(SAMPLES[interface])),
                (401, {'error': {'message': 'invalid or inactive provider key'}}),
                ProxyTimeout('no answer within 30 s'),
            ]
            for outcome in outcomes:
                with self.subTest(interface=interface, outcome=outcome):
                    if isinstance(outcome, Exception):
                        post_json.side_effect, post_json.return_value = outcome, None
                    else:
                        post_json.side_effect, post_json.return_value = None, outcome
                    with self.assertLogs('proxy', level='INFO') as logs:
                        try:
                            self.send(interface, history=history)
                        except ProxyError as e:
                            for text in (str(e), repr(e), e.detail, e.user_message):
                                self.assertNotIn(FAKE_KEYS[interface], text)
                    log_text = '\n'.join(logs.output)
                    for key in FAKE_KEYS.values():
                        self.assertNotIn(key, log_text)
                    self.assertNotIn(secret_text, log_text)

    def test_success_log_line_has_usage(self, post_json):
        post_json.return_value = (200, load_fixture('openai_single.json'))
        with self.assertLogs('proxy', level='INFO') as logs:
            self.send(history=HELLO)
        self.assertIn('interface=openai', logs.output[0])
        self.assertIn('input_tokens=183', logs.output[0])
        self.assertIn('output_tokens=15', logs.output[0])
