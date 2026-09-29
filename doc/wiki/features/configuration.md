# Configuration

Settings live in `config/settings.py`. Secrets come from `.env` in the repo root.

## How `.env` is loaded

`settings.py` calls `load_dotenv(BASE_DIR / ".env")` first.
If a variable is already set in the shell, the shell value wins. `.env` does not overwrite it.

Never commit `.env`. It is git-ignored. `.env.example` lists the names with no values.

## Variables

| Variable | Required | Default | Used for |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | none | `SECRET_KEY`. If missing or empty, the app stops with a clear error. |
| `DJANGO_DEBUG` | No | on | `DEBUG`. `1`, `true`, `yes`, `on` mean on. Anything else means off. |
| `DJANGO_ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | `ALLOWED_HOSTS`. Comma list. |
| `PROXY_OPENAI_API_KEY` | No | empty | Key for the proxy's OpenAI interface |
| `PROXY_ANTHROPIC_API_KEY` | No | empty | Key for the proxy's Anthropic interface |
| `PROXY_GOOGLE_API_KEY` | No | empty | Key for the proxy's Google interface |

`DEBUG` is on by default because this is a local dev app. A deploy must turn it off.

## Proxy settings

| Setting | Value | Meaning |
|---|---|---|
| `PROXY_BASE_URL` | `https://proxy.litechat.ai` | The proxy |
| `PROXY_KEYS` | `{"openai": ..., "anthropic": ..., "google": ...}` | One key per interface, from `.env` |
| `PROXY_TIMEOUT_SECONDS` | `30` | Timeout for every proxy request. No retries. |
| `PROXY_DEFAULT_MAX_TOKENS` | `1024` | Max reply length (study NOTE Q24) |

A missing proxy key becomes `""`. The app still starts, and `check` and tests still run.
`send_chat` checks the key at call time and raises `ProxyConfigError` without making a request. See [Proxy client](proxy-client.md).

Each key works only with its own interface. A wrong key gets a 401. See the study for details.

## Billing settings

| Setting | Value | Meaning |
|---|---|---|
| `BILLING_SIGNUP_GRANT_CREDITS` | `1000` | Free credits every new user gets in their personal account (study NOTE Q12). See [Billing accounts](billing-accounts.md). |

Tier prices are not settings. They live in the database and are edited in the admin.

## Logging

`LOGGING` sends the `proxy` logger to the console at INFO level, with the time and level.
So `runserver` prints one line per proxy call: tokens and time on success, the error type on failure.
The lines never contain keys or message text. See [the footgun](../footguns/proxy-logs-not-shown.md).

Chat limits that are not settings: messages can be at most 20,000 characters (`MAX_MESSAGE_CHARS` in `chat/services.py`).

## How to check the keys load (without printing them)

```
venv/bin/python manage.py shell -c "from django.conf import settings; print({k: bool(v) for k, v in settings.PROXY_KEYS.items()})"
```

It should print `True` for all three.

## Tests

`config/tests.py`:

- The admin login page returns 200.
- `PROXY_KEYS` has exactly the names `openai`, `anthropic`, `google`. Values are never read.
