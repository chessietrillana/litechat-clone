from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from proxy.errors import ProxyTimeout
from proxy.types import ChatResult

FAKE_KEYS = {'openai': 'fake-openai-key-1111', 'anthropic': 'fake-anthropic-key-2222',
             'google': 'fake-google-key-3333'}

OK = ChatResult(text='Hello there!', input_tokens=183, output_tokens=9, cached_tokens=0,
                finish_reason='stop', raw_finish_reason='end_turn', response_id='x', model='m')


@override_settings(PROXY_KEYS=FAKE_KEYS)
@mock.patch('proxy.management.commands.proxy_smoke.send_chat')
class ProxySmokeTests(SimpleTestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command('proxy_smoke', *args, stdout=out)
        return out.getvalue()

    def test_all_ok_prints_text_and_tokens(self, send_chat):
        send_chat.return_value = OK
        output = self.run_command()
        self.assertEqual(send_chat.call_count, 3)
        for interface in ('openai', 'anthropic', 'google'):
            self.assertIn(f'== {interface}', output)
        self.assertIn('Hello there!', output)
        self.assertIn('input_tokens=183 output_tokens=9', output)
        self.assertIn('finish=stop', output)
        self.assertIn('All interfaces OK.', output)

    def test_one_interface_only(self, send_chat):
        send_chat.return_value = OK
        self.run_command('--interface', 'google', '--prompt', 'Hi')
        send_chat.assert_called_once()
        interface, model, history = send_chat.call_args.args
        self.assertEqual((interface, model), ('google', 'gemini-3.8-flash'))
        self.assertEqual(history[0].content, 'Hi')

    def test_one_failure_does_not_stop_the_others_and_exits_non_zero(self, send_chat):
        send_chat.side_effect = [OK, ProxyTimeout('no answer within 30 s'), OK]
        out = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command('proxy_smoke', stdout=out)
        self.assertEqual(send_chat.call_count, 3)
        self.assertIn('anthropic', str(ctx.exception))
        output = out.getvalue()
        self.assertIn('FAILED ProxyTimeout', output)
        self.assertIn('== google', output)

    def test_keys_never_printed(self, send_chat):
        send_chat.side_effect = [OK, ProxyTimeout('no answer within 30 s'), OK]
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command('proxy_smoke', stdout=out)
        for key in FAKE_KEYS.values():
            self.assertNotIn(key, out.getvalue())
