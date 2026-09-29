from django.test import SimpleTestCase

from proxy.adapters import anthropic
from proxy.errors import ProxyResponseError
from proxy.tests.helpers import ANTHROPIC_401, HELLO, MULTITURN, load_fixture


class BuildRequestTests(SimpleTestCase):
    def test_path_headers_and_body(self):
        path, headers, body = anthropic.build_request('claude-haiku-4-5-20251001', MULTITURN, 1024, None)
        self.assertEqual(path, '/anthropic/v1/messages')
        self.assertEqual(headers, {'anthropic-version': '2023-06-01'})
        self.assertEqual(body['model'], 'claude-haiku-4-5-20251001')
        self.assertEqual(body['max_tokens'], 1024)
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertEqual([m['role'] for m in body['messages']], ['user', 'assistant', 'user'])
        self.assertNotIn('system', body)

    def test_system_prompt_is_top_level_field(self):
        _, _, body = anthropic.build_request('claude-haiku-4-5-20251001', HELLO, 1024, 'Be brief.')
        self.assertEqual(body['system'], 'Be brief.')
        self.assertEqual([m['role'] for m in body['messages']], ['user'])

    def test_auth_header(self):
        self.assertEqual(anthropic.auth_headers('k'), {'x-api-key': 'k'})


class ParseResponseTests(SimpleTestCase):
    def test_real_single_turn_sample(self):
        result = anthropic.parse_response(load_fixture('anthropic_single.json'))
        self.assertEqual(result.text, 'Hello! How can I help you today?')
        self.assertEqual((result.input_tokens, result.output_tokens, result.cached_tokens), (183, 9, 0))
        self.assertEqual(result.finish_reason, 'stop')
        self.assertEqual(result.raw_finish_reason, 'end_turn')
        self.assertEqual(result.response_id, '66439ce3-c134-4190-b705-af70414d3a6d')
        self.assertEqual(result.model, 'claude-haiku-4-5-20251001')

    def test_real_multiturn_sample(self):
        result = anthropic.parse_response(load_fixture('anthropic_multiturn.json'))
        self.assertEqual(result.text, 'You asked me to say hello in one sentence.')
        self.assertEqual((result.input_tokens, result.output_tokens), (203, 10))

    def test_max_tokens_is_length(self):
        result = anthropic.parse_response(load_fixture('synthetic_anthropic_max_tokens.json'))
        self.assertEqual(result.finish_reason, 'length')

    def test_thinking_block_is_left_out_and_cache_read_is_used(self):
        result = anthropic.parse_response(load_fixture('synthetic_anthropic_thinking_block.json'))
        self.assertEqual(result.text, 'Hello! How can I help you today?')
        self.assertEqual(result.cached_tokens, 128)

    def test_missing_usage_gives_none(self):
        data = load_fixture('anthropic_single.json')
        del data['usage']
        result = anthropic.parse_response(data)
        self.assertEqual((result.input_tokens, result.output_tokens, result.cached_tokens), (None, None, None))

    def test_no_content_raises(self):
        for data in ({}, {'content': None}, None):
            with self.subTest(data=data), self.assertRaises(ProxyResponseError):
                anthropic.parse_response(data)


class ParseErrorTests(SimpleTestCase):
    def test_real_401_body(self):
        self.assertEqual(anthropic.parse_error_message(ANTHROPIC_401), 'invalid or inactive provider key')
