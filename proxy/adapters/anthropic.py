"""Anthropic Messages: POST /anthropic/v1/messages."""
from proxy.adapters import error_message, int_or_none
from proxy.errors import ProxyResponseError
from proxy.types import (
    FINISH_FILTERED, FINISH_LENGTH, FINISH_OTHER, FINISH_STOP, FINISH_TOOL_CALL, ChatResult,
)

PATH = '/anthropic/v1/messages'
API_VERSION = '2023-06-01'

FINISH_REASONS = {
    'end_turn': FINISH_STOP,
    'stop_sequence': FINISH_STOP,
    'max_tokens': FINISH_LENGTH,
    'refusal': FINISH_FILTERED,
    'tool_use': FINISH_TOOL_CALL,
}


def build_request(model, history, max_tokens, system):
    body = {
        'model': model,
        'messages': [{'role': m.role, 'content': m.content} for m in history],
        'max_tokens': max_tokens,
        'thinking': {'type': 'disabled'},  # thinking off (study NOTE Q25)
    }
    if system:
        body['system'] = system
    return PATH, {'anthropic-version': API_VERSION}, body


def auth_headers(key):
    return {'x-api-key': key}


def parse_response(data):
    content = data.get('content') if isinstance(data, dict) else None
    if not isinstance(content, list):
        raise ProxyResponseError('reply has no content blocks')
    # Only text blocks are the answer; thinking and tool blocks are skipped.
    text = ''.join(b.get('text', '') for b in content if b.get('type') == 'text')
    raw_finish = data.get('stop_reason')
    usage = data.get('usage') or {}
    return ChatResult(
        text=text,
        input_tokens=int_or_none(usage.get('input_tokens')),
        output_tokens=int_or_none(usage.get('output_tokens')),
        cached_tokens=int_or_none(usage.get('cache_read_input_tokens')),
        finish_reason=FINISH_REASONS.get(raw_finish, FINISH_OTHER),
        raw_finish_reason=raw_finish,
        response_id=data.get('id'),
        model=data.get('model'),
    )


def parse_error_message(data):
    return error_message(data)
