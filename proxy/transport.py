"""The only code that talks HTTP to the proxy.

One POST, one timeout, no retries. Headers (which hold the key) are never
put into errors or logs.
"""
import json
import urllib.error
import urllib.request

from proxy.errors import ProxyConnectionError, ProxyResponseError, ProxyTimeout


def post_json(url, headers, body, timeout):
    """POST `body` as JSON. Return (status, data) for any HTTP status.

    `data` is the parsed JSON body. For an error status whose body is not
    JSON (e.g. an HTML 502 page), `data` is None. A 2xx body that is not JSON
    raises ProxyResponseError.
    """
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method='POST',
        headers={**headers, 'Content-Type': 'application/json'},
    )
    try:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
    except TimeoutError:
        raise ProxyTimeout(f'no answer within {timeout} s') from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            raise ProxyTimeout(f'no answer within {timeout} s') from None
        raise ProxyConnectionError(f'could not connect: {e.reason}') from None
    except OSError as e:  # connection reset, TLS errors, ...
        raise ProxyConnectionError(f'connection failed: {type(e).__name__}') from None

    try:
        return status, json.loads(raw)
    except ValueError:
        if 200 <= status < 300:
            raise ProxyResponseError('reply body is not JSON', status=status) from None
        return status, None
