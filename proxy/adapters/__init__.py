"""One adapter per proxy interface.

Each adapter module has pure functions (no network):
- build_request(model, history, max_tokens, system) -> (path, headers, body)
- auth_headers(key) -> dict
- parse_response(data) -> ChatResult
- parse_error_message(data) -> str
"""


def int_or_none(value):
    return value if isinstance(value, int) else None


def error_message(data):
    """Read error.message from the error body shapes all three interfaces use."""
    if isinstance(data, dict) and isinstance(data.get('error'), dict):
        return str(data['error'].get('message', ''))
    return ''
