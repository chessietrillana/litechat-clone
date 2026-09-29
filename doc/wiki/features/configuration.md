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

- `PROXY_BASE_URL = "https://proxy.litechat.ai"`
- `PROXY_KEYS = {"openai": ..., "anthropic": ..., "google": ...}`

A missing proxy key becomes `""`. The app still starts, and `check` and tests still run.
Code that calls the proxy must check the key and give a clear error. (No such code exists yet.)

Each key works only with its own interface. A wrong key gets a 401. See the study for details.

## How to check the keys load (without printing them)

```
venv/bin/python manage.py shell -c "from django.conf import settings; print({k: bool(v) for k, v in settings.PROXY_KEYS.items()})"
```

It should print `True` for all three.

## Tests

`config/tests.py`:

- The admin login page returns 200.
- `PROXY_KEYS` has exactly the names `openai`, `anthropic`, `google`. Values are never read.
