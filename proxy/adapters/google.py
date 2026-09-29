"""Google Gemini: POST /google/v1beta/models/<model>:generateContent."""
from urllib.parse import quote

from proxy.adapters import error_message, int_or_none
from proxy.errors import ProxyResponseError
from proxy.types import (
    FINISH_FILTERED, FINISH_LENGTH, FINISH_OTHER, FINISH_STOP, FINISH_TOOL_CALL, ChatResult,
)

FINISH_REASONS = {
    'STOP': FINISH_STOP,
    'MAX_TOKENS': FINISH_LENGTH,
    'SAFETY': FINISH_FILTERED,
    'RECITATION': FINISH_FILTERED,
    'BLOCKLIST': FINISH_FILTERED,
    'PROHIBITED_CONTENT': FINISH_FILTERED,
    'SPII': FINISH_FILTERED,
}

# Google calls the assistant "model".
ROLE_NAMES = {'user': 'user', 'assistant': 'model'}


def build_request(model, history, max_tokens, system):
    path = f'/google/v1beta/models/{quote(model, safe="")}:generateContent'
    body = {
        'contents': [
            {'role': ROLE_NAMES[m.role], 'parts': [{'text': m.content}]} for m in history
        ],
        'generationConfig': {
            'maxOutputTokens': max_tokens,
            'thinkingConfig': {'thinkingBudget': 0},  # thinking off (study NOTE Q25)
        },
    }
    if system:
        body['systemInstruction'] = {'parts': [{'text': system}]}
    return path, {}, body


def auth_headers(key):
    return {'x-goog-api-key': key}


def parse_response(data):
    if not isinstance(data, dict) or ('candidates' not in data and 'promptFeedback' not in data):
        raise ProxyResponseError('reply has no candidates')
    usage = data.get('usageMetadata') or {}
    candidates = data.get('candidates') or []

    if candidates:
        candidate = candidates[0]
        parts = (candidate.get('content') or {}).get('parts') or []
        # Thought parts are reasoning, not the answer.
        text = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
        raw_finish = candidate.get('finishReason')
        if any('functionCall' in p for p in parts):
            finish = FINISH_TOOL_CALL
        else:
            finish = FINISH_REASONS.get(raw_finish, FINISH_OTHER)
    else:
        # No candidates: the prompt itself was blocked.
        text = ''
        raw_finish = (data.get('promptFeedback') or {}).get('blockReason')
        finish = FINISH_FILTERED

    return ChatResult(
        text=text,
        input_tokens=int_or_none(usage.get('promptTokenCount')),
        output_tokens=int_or_none(usage.get('candidatesTokenCount')),
        cached_tokens=int_or_none(usage.get('cachedContentTokenCount')),
        finish_reason=finish,
        raw_finish_reason=raw_finish,
        response_id=data.get('responseId'),
        model=data.get('modelVersion'),
    )


def parse_error_message(data):
    return error_message(data)
