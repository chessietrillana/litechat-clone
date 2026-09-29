"""OpenAI Chat Completions: POST /openai/v1/chat/completions."""
from proxy.adapters import error_message, int_or_none
from proxy.errors import ProxyResponseError
from proxy.types import (
    FINISH_FILTERED, FINISH_LENGTH, FINISH_OTHER, FINISH_STOP, FINISH_TOOL_CALL, ChatResult,
)

PATH = '/openai/v1/chat/completions'

FINISH_REASONS = {
    'stop': FINISH_STOP,
    'length': FINISH_LENGTH,
    'content_filter': FINISH_FILTERED,
    'tool_calls': FINISH_TOOL_CALL,
}


def build_request(model, history, max_tokens, system):
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages += [{'role': m.role, 'content': m.content} for m in history]
    body = {
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'reasoning_effort': 'none',  # thinking off (study NOTE Q25)
    }
    return PATH, {}, body


def auth_headers(key):
    return {'Authorization': f'Bearer {key}'}


def parse_response(data):
    choices = data.get('choices') if isinstance(data, dict) else None
    if not choices:
        raise ProxyResponseError('reply has no choices')
    choice = choices[0]
    raw_finish = choice.get('finish_reason')
    usage = data.get('usage') or {}
    cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
    if cached is None:
        cached = usage.get('prompt_cache_hit_tokens')
    return ChatResult(
        text=(choice.get('message') or {}).get('content') or '',
        input_tokens=int_or_none(usage.get('prompt_tokens')),
        output_tokens=int_or_none(usage.get('completion_tokens')),
        cached_tokens=int_or_none(cached),
        finish_reason=FINISH_REASONS.get(raw_finish, FINISH_OTHER),
        raw_finish_reason=raw_finish,
        response_id=data.get('id'),
        model=data.get('model'),
    )


def parse_error_message(data):
    return error_message(data)
