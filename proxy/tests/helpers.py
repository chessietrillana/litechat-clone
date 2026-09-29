import json
from pathlib import Path

from proxy.types import Message

FIXTURES = Path(__file__).parent / 'fixtures'

HELLO = [Message('user', 'Say hello in one sentence.')]
MULTITURN = HELLO + [
    Message('assistant', 'Hello there!'),
    Message('user', 'What did I ask you to do first? One short sentence.'),
]

# Real 401 bodies captured in the study (doc/study/1790660517_litechat-core.md, section 4).
OPENAI_401 = {'error': {'code': 'Unauthorized', 'message': 'invalid or inactive provider key',
                        'param': None, 'type': 'authentication_error'}}
ANTHROPIC_401 = {'type': 'error', 'error': {'message': 'invalid or inactive provider key',
                                            'type': 'authentication_error'}}
GOOGLE_401 = {'error': {'code': 401, 'message': 'invalid or inactive provider key',
                        'status': 'UNAUTHORIZED'}}


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())
