# Plan: proxy client

Based on: `doc/study/1790660517_litechat-core.md` (build order item 4; sections 3, 4, 5, 7, 8, 9, 12).

Goal: one Python function the rest of the app calls to send a chat history to the proxy and get back the reply text and token usage.
It works the same way for all three interfaces. Views never touch provider JSON.

No UI, no models, no billing in this plan. The chat plan will call this code later.

Branch: `feat/proxy-client`, made from `main`.

## The function the app will call

```python
from proxy.client import send_chat
from proxy.types import Message

result = send_chat(
    interface="anthropic",                 # "openai" | "anthropic" | "google"
    model="claude-haiku-4-5-20251001",     # the proxy model ID
    history=[Message("user", "Hi"), Message("assistant", "Hello!"), Message("user", "Tell me a joke")],
    max_tokens=1024,                       # optional
    system=None,                           # optional system prompt
)

result.text            # reply text
result.input_tokens    # int, or None if the proxy sent no usage
result.output_tokens   # int, or None
result.cached_tokens   # int, or None
result.finish_reason   # "stop" | "length" | "filtered" | "tool_call" | "other"
result.raw_finish_reason   # what the proxy actually sent, e.g. "end_turn"
result.response_id     # the proxy's response ID (None for Google, which sends none)
result.model           # model name the proxy reported
```

On failure it raises one of the errors below. It never returns half a result.

## Decisions made in this plan

- **Where the code lives:** a new Django app `proxy` with no models. It needs to be an app so it can have a management command.
  - `types.py`: `Message` and `ChatResult`
  - `errors.py`
  - `transport.py`: the only code that does HTTP
  - `adapters/openai.py`, `adapters/anthropic.py`, `adapters/google.py`
  - `client.py`: `send_chat`
- **HTTP:** stdlib `urllib.request`. No new packages (study section 8).
- **Interfaces used:** OpenAI Chat Completions, Anthropic Messages, Google generateContent. Not OpenAI Responses (study section 12).
- **Adapters are pure functions.** Each adapter has:
  - `build_request(model, history, max_tokens, system)`, which returns the URL path, the headers (without the key), and the JSON body.
  - `parse_response(data)`, which returns a `ChatResult`.
  - `parse_error_message(data)`, which returns the error text from an error body.
  - They do no network calls, so tests can feed them the saved sample JSON.
- **Timeout:**
  - 30 seconds on every request. This is `PROXY_TIMEOUT_SECONDS = 30` in settings.
  - No automatic retry, ever. This follows the proxy docs and our footgun `proxy-timeouts.md`.
- **Key handling:**
  - `send_chat` reads the key from `settings.PROXY_KEYS[interface]` at call time.
  - If the key is empty, it raises `ProxyConfigError` without making a request.
  - Keys are never put in error messages or logs. A test checks this.
- **Thinking/reasoning is always off** for now:
  - OpenAI: `reasoning_effort: "none"`
  - Anthropic: `thinking: {"type": "disabled"}`
  - Google: `thinkingBudget: 0`
  - This is the study's recommendation for Q25. It is not a parameter yet. We can add one if you decide otherwise.
- **`max_tokens`:**
  - Default is `PROXY_DEFAULT_MAX_TOKENS = 1024` in settings.
  - This is a placeholder until you answer Q24. Callers can pass another value.
- **`system`:**
  - Optional. It defaults to `None`, meaning no system prompt (Q26 is still open).
  - When given: OpenAI gets a `system` message first, Anthropic gets a top-level `system` field, and Google gets `systemInstruction`.
- **History rules (checked before any request):**
  - The history is not empty.
  - Every role is `user` or `assistant`.
  - The first and last messages are from `user`.
  - Content is a non-empty string.
  - Breaking a rule raises `ValueError`. That is a bug in our code, not a user error.
- **Google role:** `assistant` becomes `model`, and text goes in `parts`.
- **Reply text:**
  - OpenAI: `choices[0].message.content`.
  - Anthropic: all `text` blocks, joined.
  - Google: all text parts of the first candidate, joined. Parts marked `thought: true` are skipped.
- **Usage:**
  - Missing usage does not raise an error. The token fields are `None`.
  - The billing plan decides what to do with that. The study recommends not charging.
- **Finish reasons, normalized:**

  | Normalized | OpenAI | Anthropic | Google |
  |---|---|---|---|
  | `stop` | `stop` | `end_turn`, `stop_sequence` | `STOP` |
  | `length` | `length` | `max_tokens` | `MAX_TOKENS` |
  | `filtered` | `content_filter` | `refusal` | `SAFETY`, `RECITATION`, `BLOCKLIST`, `PROHIBITED_CONTENT`, `SPII`, or no candidates |
  | `tool_call` | `tool_calls` | `tool_use` | (function-call part) |
  | `other` | anything else | anything else | anything else |

- **Errors** (all subclasses of `ProxyError`). Each has a short, plain `user_message` that the chat page can show as is:

  | Error | When | `user_message` |
  |---|---|---|
  | `ProxyConfigError` | Missing key, unknown interface | "This model is not set up. Please tell the site admin." |
  | `ProxyTimeout` | No full answer within 30 s | "The model took too long to answer. Please try again." |
  | `ProxyConnectionError` | DNS, TLS, or connection failure | "Could not reach the model service. Please try again." |
  | `ProxyAuthError` | 401, 403 | "This model is not set up. Please tell the site admin." |
  | `ProxyRateLimitError` | 429 | "Too many requests right now. Please wait a moment and try again." |
  | `ProxyBadRequestError` | 400, other 4xx | "The model could not handle this request." |
  | `ProxyUpstreamError` | 5xx | "The model service had a problem. Please try again later." |
  | `ProxyResponseError` | 200 but the body is not JSON or has no reply | "The model sent a reply we could not read." |

  Each error also keeps `status` (HTTP status or `None`) and `detail` (the proxy's error message, for logs and admins).
- **Logging:**
  - Each call logs one line to the `proxy` logger: interface, model, HTTP status, time taken, and token counts.
  - It never logs message text or keys.
- **Test data:**
  - The real sample responses from the study are copied into `proxy/tests/fixtures/`, so tests do not depend on the docs folder.
  - Shapes we never captured are hand-written and named `synthetic_*.json`: cut-off replies, error bodies other than 401, a Google blocked prompt, missing usage. They follow the proxy docs and provider docs.
  - The study lists these as untested (section 11).
- **Live check:** a management command `proxy_smoke`. Tests never touch the network. The live command is run by hand.

## Steps

- [x] **1. Proxy app, types, errors, and HTTP transport**
  - Change during execution: an error status (4xx/5xx) with a body that is not JSON, such as an HTML 502 page, returns `(status, None)` instead of raising `ProxyResponseError`. That way `send_chat` still maps it by status (e.g. 502 → `ProxyUpstreamError`). Only a 2xx body that is not JSON raises `ProxyResponseError`.
  - Files:
    - `proxy/` (new app, `venv/bin/python manage.py startapp proxy`). Delete nothing, but leave `models.py`, `admin.py`, and `views.py` empty.
    - Add `"proxy"` to `INSTALLED_APPS`.
    - `proxy/types.py`: `Message` and `ChatResult` (frozen dataclasses).
    - `proxy/errors.py`: the error classes in the table above.
    - `proxy/transport.py`: `post_json(url, headers, body, timeout) -> (status, data)`.
      - It returns the status and parsed JSON for any HTTP status, including 4xx and 5xx.
      - A timeout raises `ProxyTimeout`. Other network or TLS failures raise `ProxyConnectionError`.
      - A body that is not JSON raises `ProxyResponseError`.
    - `config/settings.py`: `PROXY_TIMEOUT_SECONDS = 30`, `PROXY_DEFAULT_MAX_TOKENS = 1024`.
    - `proxy/tests/__init__.py`, `proxy/tests/test_transport.py`. Remove the generated `proxy/tests.py`, which clashes with the `tests/` package. It is an empty generated stub, so no work is lost.
  - Tests (`urllib.request.urlopen` is mocked):
    - Sends POST, JSON body, `Content-Type: application/json`, and the given headers.
    - Passes `timeout=30` to `urlopen`.
    - 200 and 401 both return `(status, parsed JSON)`.
    - A socket timeout raises `ProxyTimeout`, and `urlopen` is called exactly once (no retry).
    - A `URLError` raises `ProxyConnectionError`.
    - A non-JSON body raises `ProxyResponseError`.
    - A fake key in the headers never shows up in the text of any raised error.
  - Commit: `feat: add proxy app with HTTP transport and errors`

- [x] **2. OpenAI Chat Completions adapter**
  - Files: `proxy/adapters/__init__.py`, `proxy/adapters/openai.py`, `proxy/tests/fixtures/openai_single.json`, `openai_multiturn.json` (copied from the study), `synthetic_openai_length.json`, `synthetic_openai_no_usage.json`, `proxy/tests/test_openai.py`.
  - Tests:
    - `build_request`:
      - The path is `/openai/v1/chat/completions`.
      - The body has `model`, `messages`, `max_tokens`, and `reasoning_effort: "none"`.
      - A system prompt becomes the first message.
    - `parse_response` on the real samples gives:
      - the right text
      - `input_tokens` 183 and 203, `output_tokens` 15 and 10
      - `cached_tokens` 0
      - `finish_reason` `stop`
      - the response ID
    - Cut-off sample gives `length`. The no-usage sample gives token fields `None`.
    - `parse_error_message` reads the real 401 body from the study.
  - Commit: `feat: add OpenAI chat completions adapter`

- [ ] **3. Anthropic Messages adapter**
  - Files: `proxy/adapters/anthropic.py`, `proxy/tests/fixtures/anthropic_single.json`, `anthropic_multiturn.json`, `synthetic_anthropic_max_tokens.json`, `synthetic_anthropic_thinking_block.json`, `proxy/tests/test_anthropic.py`.
  - Tests:
    - `build_request`:
      - The path is `/anthropic/v1/messages`.
      - The headers include `anthropic-version: 2023-06-01`.
      - The body has `thinking: {"type": "disabled"}` and `max_tokens`.
      - A system prompt goes in the top-level `system` field, not in `messages`.
    - `parse_response` on the real samples gives:
      - the right text
      - 183/9 and 203/10 tokens
      - `cached_tokens` from `cache_read_input_tokens`
      - `stop`
    - `max_tokens` sample gives `length`. Thinking blocks are left out of `text`.
    - `parse_error_message` reads the real 401 body.
  - Commit: `feat: add Anthropic messages adapter`

- [ ] **4. Google generateContent adapter**
  - Files: `proxy/adapters/google.py`, `proxy/tests/fixtures/google_multiturn.json`, `synthetic_google_max_tokens.json`, `synthetic_google_blocked_prompt.json`, `synthetic_google_thought_part.json`, `proxy/tests/test_google.py`.
  - Tests:
    - `build_request`:
      - The path is `/google/v1beta/models/<model>:generateContent`, with the model in the URL.
      - Role `assistant` becomes `model`, and text goes in `parts`.
      - `generationConfig` has `maxOutputTokens` and `thinkingConfig.thinkingBudget: 0`.
      - A system prompt goes in `systemInstruction`.
    - `parse_response` on the real sample gives:
      - the right text
      - 203/10 tokens
      - `stop`
      - `model` from `modelVersion`
      - `response_id` `None`
    - `MAX_TOKENS` gives `length`. A blocked prompt (no candidates) gives `filtered` and empty text. Thought parts are skipped.
    - `parse_error_message` reads the real 401 body.
  - Commit: `feat: add Google generateContent adapter`

- [ ] **5. `send_chat` entry point**
  - Files:
    - `proxy/client.py`: `send_chat(...)`. It does these in order:
      1. checks the interface and the history
      2. reads the key
      3. builds the request with the adapter
      4. adds the auth header
      5. calls `transport.post_json`
      6. maps a non-200 status to the right error
      7. parses the response
      8. logs one line
    - `proxy/tests/test_client.py`.
  - Tests (`transport.post_json` is mocked; no network):
    - For each interface, the right URL and the right auth header are used:
      - OpenAI: `Authorization: Bearer`
      - Anthropic: `x-api-key`
      - Google: `x-goog-api-key`
    - Returns a `ChatResult` from the sample JSON.
    - An unknown interface raises `ProxyConfigError`. An empty key (via `override_settings`) raises `ProxyConfigError`, and the transport is not called.
    - Bad history (empty, last message from the assistant, wrong role, empty content) raises `ValueError`, and the transport is not called.
    - The status maps to the error:
      - 400 → `ProxyBadRequestError`
      - 401 and 403 → `ProxyAuthError`
      - 429 → `ProxyRateLimitError`
      - 500, 502, 503, 504 → `ProxyUpstreamError`
    - Each error carries the proxy's message in `detail` and a non-empty `user_message`.
    - A 200 with no reply at all (e.g. `{}`) raises `ProxyResponseError`.
    - A fake key never appears in any error text or in the captured log output (`assertLogs`).
    - The log line has no message text.
    - `max_tokens` defaults to `PROXY_DEFAULT_MAX_TOKENS`, and `timeout` to `PROXY_TIMEOUT_SECONDS`.
  - Commit: `feat: add send_chat proxy client`

- [ ] **6. `proxy_smoke` management command**
  - Files: `proxy/management/__init__.py`, `proxy/management/commands/__init__.py`, `proxy/management/commands/proxy_smoke.py`, `proxy/tests/test_smoke_command.py`.
  - Usage: `venv/bin/python manage.py proxy_smoke [--interface openai|anthropic|google|all] [--prompt "..."]`. The default is `all` and "Say hello in one sentence."
  - For each interface it:
    - sends one live request with the model ID from the study
    - prints the reply text, token counts, finish reason, and time taken
    - on an error, prints the error class and `detail`, then goes on to the next interface
    - exits with a non-zero code if any interface failed
  - It never prints keys or headers.
  - Tests (`send_chat` is mocked): output has text and tokens, one failure does not stop the others, a failure gives a non-zero exit code, and no key appears in the output.
  - Live check (done once by Claude, 30 s timeout each, no retries): `venv/bin/python manage.py proxy_smoke`.
    - Report the result for each interface.
    - A timeout is reported as it is, not hidden. If it happens, run that interface once more by hand and report both results.
  - Commit: `feat: add proxy_smoke management command`

- [ ] **7. Record anything surprising (only if needed)**
  - If steps 1–6 or the live check find surprising behavior, record it in `doc/wiki/footguns/`.
  - If nothing is surprising, skip this step and say so.
  - Commit: `docs: record proxy client footguns`

## Done when

- `venv/bin/python manage.py check` and `venv/bin/python manage.py test` pass, with no network use in tests.
- `migrate` has nothing to apply. (This plan adds no models.)
- The live `proxy_smoke` run has been reported for all three interfaces.
- `git grep` finds no key values in tracked files. (Checked with a script that prints only a count.)

## At rendezvous (human does this)

There is no web page to click this time. In your own terminal:

1. `cd /Users/chessietrillana/litechat-clone && venv/bin/python manage.py proxy_smoke`
2. You should see three blocks (openai, anthropic, google). Each has a one-sentence hello, input tokens around 183, a small output token count, and finish reason `stop`.
3. If one says `ProxyTimeout`, run `venv/bin/python manage.py proxy_smoke --interface <that one>` again. Timeouts are a known proxy issue (`doc/wiki/footguns/proxy-timeouts.md`).
4. Check that no key appears anywhere in the output.

## Open questions this plan works around (answer before the chat plan)

- Q24: max reply length. For now the default is 1024 tokens, and callers can change it.
- Q25: thinking. Off for now.
- Q26: system prompt. None for now. `send_chat` already supports one.
