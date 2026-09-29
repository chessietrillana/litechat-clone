# Overview

## What the app does

Litechat clone. A web app that gives users metered, pay-as-you-go access to LLMs from several providers.
The LLMs come through the proxy at https://proxy.litechat.ai.

**Status (2026-09-29):**

- Built:
  - project setup
  - sign up / log in / log out
  - the proxy client (`send_chat`, not yet used by any page)
  - the model catalog: three models with provider and tier, a Models page, and on/off in the admin
- Not built yet: chat and billing. The home page only says hello and links to Models.

Planned features are in [TODO.md](../../TODO.md). The full study is in `doc/study/1790660517_litechat-core.md`.

## Features

- [Configuration](features/configuration.md): settings and `.env`.
- [Auth](features/auth.md): sign up, log in, log out, home page.
- [Proxy client](features/proxy-client.md): `send_chat()` and the `proxy_smoke` live check.
- [Model catalog](features/model-catalog.md): `LLMModel`, the Models page, turning models on and off.

## Stack

- Python 3.11, Django 5.2, SQLite.
- Django built-in auth and admin. Server-rendered templates. No frontend framework.
- `python-dotenv` loads `.env`.
- Exact versions are in `requirements.txt`.

## How to run it

1. Use the venv in `./venv`. Install packages:
   ```
   venv/bin/pip install -r requirements.txt
   ```
2. Make a `.env` file in the repo root. Copy `.env.example` and fill in the values. `DJANGO_SECRET_KEY` is required. See [Configuration](features/configuration.md).
3. Set up the database. This also adds the three models to the catalog.
   ```
   venv/bin/python manage.py migrate
   ```
4. Create an admin user. Run this in your own terminal, so the password stays out of any AI transcript:
   ```
   venv/bin/python manage.py createsuperuser
   ```
5. Start the server:
   ```
   venv/bin/python manage.py runserver
   ```
6. Open http://127.0.0.1:8000/. You are sent to the login page. Sign up, or log in.
7. The admin is at http://127.0.0.1:8000/admin/.

## How to check it

```
venv/bin/python manage.py check
venv/bin/python manage.py test
```

Tests do not call the proxy and do not need real keys.

To check the real proxy (uses the network and your keys):

```
venv/bin/python manage.py proxy_smoke
```

## Known problems

See [footguns](footguns/):

- [Python HTTPS certificates on macOS](footguns/python-ssl-certificates-macos.md)
- [Proxy requests can hang](footguns/proxy-timeouts.md)
- [Django logout needs a POST](footguns/django-logout-requires-post.md)
- [Proxy log lines are not shown yet](footguns/proxy-logs-not-shown.md)
