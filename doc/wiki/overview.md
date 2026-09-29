# Overview

## What the app does

Litechat clone. A web app that gives users metered, pay-as-you-go access to LLMs from several providers.
The LLMs come through the proxy at https://proxy.litechat.ai.

**Status (2026-09-29):** only the project setup is built. There is an empty Django project with the admin.
No user-facing features yet. Next up: sign up, log in, log out.

Planned features are in [TODO.md](../../TODO.md). The full study is in `doc/study/1790660517_litechat-core.md`.

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
3. Set up the database:
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
6. Open http://127.0.0.1:8000/admin/.

## How to check it

```
venv/bin/python manage.py check
venv/bin/python manage.py test
```

Tests do not call the proxy and do not need real keys.

## Known problems

See [footguns](footguns/):

- [Python HTTPS certificates on macOS](footguns/python-ssl-certificates-macos.md)
- [Proxy requests can hang](footguns/proxy-timeouts.md)
