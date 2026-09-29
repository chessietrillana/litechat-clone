from django.test import SimpleTestCase

from proxy.adapters import openai
from proxy.errors import ProxyResponseError
from proxy.tests.helpers import HELLO, MULTITURN, OPENAI_401, load_fixture


class BuildRequestTests(SimpleTestCase):
    def test_path_and_body(self):
        path, headers, body = openai.build_request('gpt-5.6-luna', MULTITURN, 1024, None)
        self.assertEqual(path, '/openai/v1/chat/completions')
        self.assertEqual(headers, {})
        self.assertEqual(body['model'], 'gpt-5.6-luna')
        self.assertEqual(body['max_tokens'], 1024)
        self.assertEqual(body['reasoning_effort'], 'none')
        self.assertEqual(body['messages'], [
            {'role': 'user', 'content': 'Say hello in one sentence.'},
            {'role': 'assistant', 'content': 'Hello there!'},
            {'role': 'user', 'content': 'What did I ask you to do first? One short sentence.'},
        ])

    def test_system_prompt_is_first_message(self):
        _, _, body = openai.build_request('gpt-5.6-luna', HELLO, 1024, 'Be brief.')
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': 'Be brief.'})
        self.assertEqual(body['messages'][1]['role'], 'user')

    def test_no_system_message_when_none(self):
        _, _, body = openai.build_request('gpt-5.6-luna', HELLO, 1024, None)
        self.assertEqual([m['role'] for m in body['messages']], ['user'])

    def test_auth_header(self):
        self.assertEqual(openai.auth_headers('k'), {'Authorization': 'Bearer k'})


class ParseResponseTests(SimpleTestCase):
    def test_real_single_turn_sample(self):
        result = openai.parse_response(load_fixture('openai_single.json'))
        self.assertEqual(result.text, "Hello! I'm GPT, ready to help you with whatever you need.")
        self.assertEqual((result.input_tokens, result.output_tokens, result.cached_tokens), (183, 15, 0))
        self.assertEqual(result.finish_reason, 'stop')
        self.assertEqual(result.raw_finish_reason, 'stop')
        self.assertEqual(result.response_id, '158ec8b0-5dfe-45ab-93a9-8b9bc9259c5a')
        self.assertEqual(result.model, 'gpt-5.6-luna')

    def test_real_multiturn_sample(self):
        result = openai.parse_response(load_fixture('openai_multiturn.json'))
        self.assertEqual(result.text, 'You asked me to say hello in one sentence.')
        self.assertEqual((result.input_tokens, result.output_tokens), (203, 10))

    def test_cut_off_reply_is_length(self):
        result = openai.parse_response(load_fixture('synthetic_openai_length.json'))
        self.assertEqual(result.finish_reason, 'length')

    def test_missing_usage_gives_none(self):
        result = openai.parse_response(load_fixture('synthetic_openai_no_usage.json'))
        self.assertEqual(result.text, 'Hello!')
        self.assertEqual((result.input_tokens, result.output_tokens, result.cached_tokens), (None, None, None))

    def test_unknown_finish_reason_is_other(self):
        data = load_fixture('openai_single.json')
        data['choices'][0]['finish_reason'] = 'something_new'
        self.assertEqual(openai.parse_response(data).finish_reason, 'other')

    def test_no_choices_raises(self):
        for data in ({}, {'choices': []}, None):
            with self.subTest(data=data), self.assertRaises(ProxyResponseError):
                openai.parse_response(data)


class ParseErrorTests(SimpleTestCase):
    def test_real_401_body(self):
        self.assertEqual(openai.parse_error_message(OPENAI_401), 'invalid or inactive provider key')

    def test_unreadable_body_gives_empty_string(self):
        self.assertEqual(openai.parse_error_message(None), '')
