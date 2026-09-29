import io
import json
import socket
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from proxy import transport
from proxy.errors import ProxyConnectionError, ProxyResponseError, ProxyTimeout

URL = 'https://proxy.example/openai/v1/chat/completions'
FAKE_KEY = 'sk-fake-key-for-tests-0000'
HEADERS = {'Authorization': f'Bearer {FAKE_KEY}'}
BODY = {'model': 'm', 'messages': []}


def fake_response(status, raw):
    response = mock.MagicMock()
    response.status = status
    response.read.return_value = raw
    response.__enter__.return_value = response
    return response


def http_error(status, raw):
    return urllib.error.HTTPError(URL, status, 'error', {}, io.BytesIO(raw))


@mock.patch('proxy.transport.urllib.request.urlopen')
class PostJsonTests(SimpleTestCase):
    def call(self):
        return transport.post_json(URL, HEADERS, BODY, timeout=30)

    def test_sends_json_post_with_headers_and_timeout(self, urlopen):
        urlopen.return_value = fake_response(200, b'{"ok": true}')
        self.call()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.full_url, URL)
        self.assertEqual(json.loads(request.data), BODY)
        self.assertEqual(request.get_header('Content-type'), 'application/json')
        self.assertEqual(request.get_header('Authorization'), f'Bearer {FAKE_KEY}')
        self.assertEqual(urlopen.call_args.kwargs['timeout'], 30)

    def test_200_returns_status_and_json(self, urlopen):
        urlopen.return_value = fake_response(200, b'{"ok": true}')
        self.assertEqual(self.call(), (200, {'ok': True}))

    def test_401_returns_status_and_json(self, urlopen):
        urlopen.side_effect = http_error(401, b'{"error": {"message": "invalid or inactive provider key"}}')
        status, data = self.call()
        self.assertEqual(status, 401)
        self.assertEqual(data['error']['message'], 'invalid or inactive provider key')

    def test_error_status_with_non_json_body_returns_none(self, urlopen):
        urlopen.side_effect = http_error(502, b'<html>Bad Gateway</html>')
        self.assertEqual(self.call(), (502, None))

    def test_timeout_raises_and_does_not_retry(self, urlopen):
        urlopen.side_effect = socket.timeout('timed out')
        with self.assertRaises(ProxyTimeout):
            self.call()
        self.assertEqual(urlopen.call_count, 1)

    def test_wrapped_timeout_raises_proxy_timeout(self, urlopen):
        urlopen.side_effect = urllib.error.URLError(TimeoutError('timed out'))
        with self.assertRaises(ProxyTimeout):
            self.call()
        self.assertEqual(urlopen.call_count, 1)

    def test_timeout_while_reading_body_raises_proxy_timeout(self, urlopen):
        response = fake_response(200, b'')
        response.read.side_effect = TimeoutError('timed out')
        urlopen.return_value = response
        with self.assertRaises(ProxyTimeout):
            self.call()

    def test_url_error_raises_connection_error(self, urlopen):
        urlopen.side_effect = urllib.error.URLError('nodename nor servname provided')
        with self.assertRaises(ProxyConnectionError):
            self.call()

    def test_connection_reset_raises_connection_error(self, urlopen):
        urlopen.side_effect = ConnectionResetError('reset')
        with self.assertRaises(ProxyConnectionError):
            self.call()

    def test_non_json_200_raises_response_error(self, urlopen):
        urlopen.return_value = fake_response(200, b'not json')
        with self.assertRaises(ProxyResponseError):
            self.call()

    def test_key_never_appears_in_errors(self, urlopen):
        failures = [
            socket.timeout('timed out'),
            urllib.error.URLError('down'),
            ConnectionResetError('reset'),
        ]
        for failure in failures:
            urlopen.side_effect = failure
            with self.subTest(failure=type(failure).__name__):
                with self.assertRaises(Exception) as ctx:
                    self.call()
                self.assertNotIn(FAKE_KEY, str(ctx.exception))
                self.assertNotIn(FAKE_KEY, repr(ctx.exception))
                self.assertIsNone(ctx.exception.__cause__)
