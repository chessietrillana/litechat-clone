# Proxy client

One function, `send_chat`, sends a chat history to the proxy and returns the reply and token usage.
It works the same way for the OpenAI, Anthropic, and Google interfaces. Nothing else in the app should talk to the proxy.

There is no UI for this yet. The chat plan will use it.

Plan: `doc/plan/1790662553_proxy-client.md`. Study: `doc/study/1790660517_litechat-core.md`.

## How to use it

```python
from proxy.client import send_chat
from proxy.errors import ProxyError
from proxy.types import Message

try:
    result = send_chat(
        "anthropic",                      # "openai" | "anthropic" | "google"
        "claude-haiku-4-5-20251001",      # proxy model ID
        [Message("user", "Hi"), Message("assistant", "Hello!"), Message("user", "Tell me a joke")],
        # optional: max_tokens=..., system=..., timeout=...
    )
except ProxyError as e:
    show_to_user(e.user_message)   # plain, safe text
    log(e.detail, e.status)        # for admins
```

`result` is a `ChatResult`:

| Field | Meaning |
|---|---|
| `text` | Reply text. Thinking blocks and thought parts are left out. |
| `input_tokens`, `output_tokens`, `cached_tokens` | Token counts, or `None` if the proxy sent no usage |
| `finish_reason` | `stop`, `length` (cut off), `filtered`, `tool_call`, or `other` |
| `raw_finish_reason` | What the proxy actually sent, e.g. `end_turn` |
| `response_id` | The proxy's ID (`None` for Google, which sends none) |
| `model` | Model name the proxy reported |

## Rules it follows

- **Timeout:** 30 seconds (`PROXY_TIMEOUT_SECONDS`). **No retries.** See [proxy timeouts](../footguns/proxy-timeouts.md).
- **Keys:** read from `settings.PROXY_KEYS` at call time. They are never put in errors, logs, or command output. Tests check this.
- **Thinking is off** on all three interfaces (study NOTE Q25).
- **Max reply length:** 1024 tokens by default (`PROXY_DEFAULT_MAX_TOKENS`, study NOTE Q24).
- **System prompt:** none by default (study NOTE Q26). Pass `system=` to add one.
- **History must:**
  - not be empty
  - use only the roles `user` and `assistant`
  - start and end with `user`
  - have non-empty text in every message

  If not, `send_chat` raises `ValueError`. That is a bug in our code, so no request is made.

## Errors

All errors are subclasses of `ProxyError`. Each has `user_message`, `detail`, and `status`.

| Error | When | `user_message` |
|---|---|---|
| `ProxyConfigError` | Missing key, unknown interface | This model is not set up. Please tell the site admin. |
| `ProxyTimeout` | No answer within 30 s | The model took too long to answer. Please try again. |
| `ProxyConnectionError` | DNS, TLS, or connection failure | Could not reach the model service. Please try again. |
| `ProxyAuthError` | 401, 403 | This model is not set up. Please tell the site admin. |
| `ProxyRateLimitError` | 429 | Too many requests right now. Please wait a moment and try again. |
| `ProxyBadRequestError` | 400, other 4xx | The model could not handle this request. |
| `ProxyUpstreamError` | 5xx | The model service had a problem. Please try again later. |
| `ProxyResponseError` | 200 but no readable reply | The model sent a reply we could not read. |

## How it is built

| File | Job |
|---|---|
| `proxy/types.py` | `Message`, `ChatResult`, finish reason names |
| `proxy/errors.py` | Error classes |
| `proxy/transport.py` | The only HTTP code. One POST, one timeout, no retry. Stdlib `urllib`. |
| `proxy/adapters/openai.py` | Chat Completions: `/openai/v1/chat/completions`, `Authorization: Bearer` |
| `proxy/adapters/anthropic.py` | Messages: `/anthropic/v1/messages`, `x-api-key`, `anthropic-version` |
| `proxy/adapters/google.py` | generateContent: `/google/v1beta/models/<model>:generateContent`, `x-goog-api-key`. Role `assistant` becomes `model`. |
| `proxy/client.py` | `send_chat`: check input, read key, build request, send, map errors, parse, log |

Adapters are pure functions (`build_request`, `auth_headers`, `parse_response`, `parse_error_message`), so tests feed them saved JSON.

## Live check

```
venv/bin/python manage.py proxy_smoke                      # all three
venv/bin/python manage.py proxy_smoke --interface google   # one
venv/bin/python manage.py proxy_smoke --prompt "Hi"
```

It sends one real request per interface. It prints the reply, token counts, finish reason, and time taken.
It exits with an error if any interface failed. It never prints keys.
If one interface times out, run it again for that interface.

Last run (2026-09-29):

- All three worked. OpenAI needed a second try after a timeout.
- Each reply used 183 input tokens.

## Tests

All in `proxy/tests/`. None of them use the network.

- `test_transport.py`: POST, headers, timeout, no retry, timeout and connection errors, non-JSON bodies, no key in errors.
- `test_openai.py`, `test_anthropic.py`, `test_google.py`: request shape and parsing of real and synthetic samples.
- `test_client.py`: URLs and auth headers per interface, defaults, bad history, status → error mapping, no keys or message text in logs or errors.
- `test_smoke_command.py`: output, one failure does not stop the others, exit code, no keys.

Test data is in `proxy/tests/fixtures/`:

- Files without a prefix are real replies captured in the study.
- `synthetic_*.json` files are hand-written. They cover shapes we never saw live (cut-off replies, blocked prompts, thinking parts, missing usage).

## Known gaps

- Log lines are not shown yet. See [proxy logs not shown](../footguns/proxy-logs-not-shown.md).
- Error bodies other than 401 were never captured live. Their parsing is based on the docs.
- No streaming (out of scope).
