"""Live check: send one real request per interface and print the result.

Uses the network and real keys. Never prints keys or headers.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from proxy.client import send_chat
from proxy.errors import ProxyError
from proxy.types import Message

# The model IDs named in the proxy docs (study section 3).
SMOKE_MODELS = {
    'openai': 'gpt-5.6-luna',
    'anthropic': 'claude-haiku-4-5-20251001',
    'google': 'gemini-3.8-flash',
}


class Command(BaseCommand):
    help = 'Send one live request per proxy interface and print text, tokens, and finish reason.'

    def add_arguments(self, parser):
        parser.add_argument('--interface', choices=[*SMOKE_MODELS, 'all'], default='all')
        parser.add_argument('--prompt', default='Say hello in one sentence.')

    def handle(self, *args, **options):
        interfaces = list(SMOKE_MODELS) if options['interface'] == 'all' else [options['interface']]
        failed = []
        for interface in interfaces:
            model = SMOKE_MODELS[interface]
            self.stdout.write(f'== {interface} ({model})')
            started = time.monotonic()
            try:
                result = send_chat(interface, model, [Message('user', options['prompt'])])
            except ProxyError as e:
                seconds = time.monotonic() - started
                self.stdout.write(self.style.ERROR(
                    f'   FAILED {type(e).__name__} status={e.status} seconds={seconds:.1f} detail={e.detail}'
                ))
                failed.append(interface)
                continue
            seconds = time.monotonic() - started
            self.stdout.write(f'   text: {result.text}')
            self.stdout.write(
                f'   input_tokens={result.input_tokens} output_tokens={result.output_tokens} '
                f'cached_tokens={result.cached_tokens}'
            )
            self.stdout.write(
                f'   finish={result.finish_reason} (raw={result.raw_finish_reason}) '
                f'model={result.model} seconds={seconds:.1f}'
            )
        if failed:
            raise CommandError(f'failed: {", ".join(failed)}')
        self.stdout.write(self.style.SUCCESS('All interfaces OK.'))
