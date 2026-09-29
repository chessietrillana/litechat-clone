from django.test import SimpleTestCase

from proxy.adapters import google
from proxy.errors import ProxyResponseError
from proxy.tests.helpers import GOOGLE_401, HELLO, MULTITURN, load_fixture


class BuildRequestTests(SimpleTestCase):
    def test_path_and_body(self):
        path, headers, body = google.build_request('gemini-3.8-flash', MULTITURN, 1024, None)
        self.assertEqual(path, '/google/v1beta/models/gemini-3.8-flash:generateContent')
        self.assertEqual(headers, {})
        self.assertEqual(body['contents'], [
            {'role': 'user', 'parts': [{'text': 'Say hello in one sentence.'}]},
            {'role': 'model', 'parts': [{'text': 'Hello there!'}]},
            {'role': 'user', 'parts': [{'text': 'What did I ask you to do first? One short sentence.'}]},
        ])
        self.assertEqual(body['generationConfig'], {
            'maxOutputTokens': 1024,
            'thinkingConfig': {'thinkingBudget': 0},
        })
        self.assertNotIn('model', body)
        self.assertNotIn('systemInstruction', body)

    def test_system_prompt_is_system_instruction(self):
        _, _, body = google.build_request('gemini-3.8-flash', HELLO, 1024, 'Be brief.')
        self.assertEqual(body['systemInstruction'], {'parts': [{'text': 'Be brief.'}]})

    def test_model_name_is_escaped_in_path(self):
        path, _, _ = google.build_request('a/b:c', HELLO, 1024, None)
        self.assertEqual(path, '/google/v1beta/models/a%2Fb%3Ac:generateContent')

    def test_auth_header(self):
        self.assertEqual(google.auth_headers('k'), {'x-goog-api-key': 'k'})


class ParseResponseTests(SimpleTestCase):
    def test_real_multiturn_sample(self):
        result = google.parse_response(load_fixture('google_multiturn.json'))
        self.assertEqual(result.text, 'You asked me to say hello in one sentence.')
        self.assertEqual((result.input_tokens, result.output_tokens, result.cached_tokens), (203, 10, 0))
        self.assertEqual(result.finish_reason, 'stop')
        self.assertEqual(result.raw_finish_reason, 'STOP')
        self.assertEqual(result.model, 'gemini-3.8-flash')
        self.assertIsNone(result.response_id)

    def test_max_tokens_is_length(self):
        result = google.parse_response(load_fixture('synthetic_google_max_tokens.json'))
        self.assertEqual(result.finish_reason, 'length')

    def test_blocked_prompt_is_filtered_with_empty_text(self):
        result = google.parse_response(load_fixture('synthetic_google_blocked_prompt.json'))
        self.assertEqual(result.text, '')
        self.assertEqual(result.finish_reason, 'filtered')
        self.assertEqual(result.raw_finish_reason, 'SAFETY')
        self.assertEqual(result.input_tokens, 190)
        self.assertIsNone(result.output_tokens)

    def test_safety_finish_is_filtered(self):
        data = load_fixture('google_multiturn.json')
        data['candidates'][0]['finishReason'] = 'SAFETY'
        self.assertEqual(google.parse_response(data).finish_reason, 'filtered')

    def test_thought_parts_are_skipped(self):
        result = google.parse_response(load_fixture('synthetic_google_thought_part.json'))
        self.assertEqual(result.text, "Hello! I'm Gemini, ready to help with whatever you need.")

    def test_function_call_part_is_tool_call(self):
        data = load_fixture('google_multiturn.json')
        data['candidates'][0]['content']['parts'] = [{'functionCall': {'name': 'f', 'args': {}}}]
        self.assertEqual(google.parse_response(data).finish_reason, 'tool_call')

    def test_missing_usage_gives_none(self):
        data = load_fixture('google_multiturn.json')
        del data['usageMetadata']
        result = google.parse_response(data)
        self.assertEqual((result.input_tokens, result.output_tokens, result.cached_tokens), (None, None, None))

    def test_no_candidates_raises(self):
        for data in ({}, {'usageMetadata': {}}, None):
            with self.subTest(data=data), self.assertRaises(ProxyResponseError):
                google.parse_response(data)


class ParseErrorTests(SimpleTestCase):
    def test_real_401_body(self):
        self.assertEqual(google.parse_error_message(GOOGLE_401), 'invalid or inactive provider key')
