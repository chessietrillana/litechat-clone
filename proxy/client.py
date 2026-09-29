"""send_chat: the one function the app uses to talk to the proxy."""
import logging
import time

from django.conf import settings

from proxy import transport
from proxy.adapters import anthropic, google, openai
from proxy.errors import (
    ProxyAuthError, ProxyBadRequestError, ProxyConfigError, ProxyRateLimitError,
    ProxyUpstreamError,
)
from proxy.types import ROLES

logger = logging.getLogger('proxy')

ADAPTERS = {
    'openai': openai,
    'anthropic': anthropic,
    'google': google,
}


def send_chat(interface, model, history, *, max_tokens=None, system=None, timeout=None):
    """Send the full history to the proxy. Return a ChatResult or raise a ProxyError.

    Never retries. Never logs message text or keys.
    """
    adapter = ADAPTERS.get(interface)
    if adapter is None:
        raise ProxyConfigError(f'unknown interface {interface!r}')
    _check_history(history)
    key = settings.PROXY_KEYS.get(interface, '')
    if not key:
        raise ProxyConfigError(f'no proxy key set for {interface}')

    if max_tokens is None:
        max_tokens = settings.PROXY_DEFAULT_MAX_TOKENS
    if timeout is None:
        timeout = settings.PROXY_TIMEOUT_SECONDS

    path, headers, body = adapter.build_request(model, history, max_tokens, system)
    headers = {**headers, **adapter.auth_headers(key)}
    started = time.monotonic()
    status = None
    try:
        status, data = transport.post_json(settings.PROXY_BASE_URL + path, headers, body, timeout)
        if status != 200:
            raise _error_for_status(status, adapter.parse_error_message(data))
        result = adapter.parse_response(data)
    except Exception as e:
        logger.warning(
            'proxy call failed interface=%s model=%s status=%s seconds=%.1f error=%s',
            interface, model, status, time.monotonic() - started, type(e).__name__,
        )
        raise
    logger.info(
        'proxy call ok interface=%s model=%s status=%s seconds=%.1f '
        'input_tokens=%s output_tokens=%s cached_tokens=%s finish=%s',
        interface, model, status, time.monotonic() - started,
        result.input_tokens, result.output_tokens, result.cached_tokens, result.finish_reason,
    )
    return result


def _check_history(history):
    """History bugs are our bugs, so they raise ValueError, not a ProxyError."""
    if not history:
        raise ValueError('history is empty')
    for message in history:
        if message.role not in ROLES:
            raise ValueError(f'bad role {message.role!r}')
        if not isinstance(message.content, str) or not message.content:
            raise ValueError('message content must be a non-empty string')
    if history[0].role != 'user' or history[-1].role != 'user':
        raise ValueError('history must start and end with a user message')


def _error_for_status(status, detail):
    if status in (401, 403):
        error_class = ProxyAuthError
    elif status == 429:
        error_class = ProxyRateLimitError
    elif status >= 500:
        error_class = ProxyUpstreamError
    else:
        error_class = ProxyBadRequestError
    return error_class(detail, status=status)
