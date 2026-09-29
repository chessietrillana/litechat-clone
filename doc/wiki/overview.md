# Overview

## What the app does

Litechat clone. A web app that gives users metered, pay-as-you-go access to LLMs from several providers.
The LLMs come through the proxy at https://proxy.litechat.ai.

**Status (2026-09-29):**

- Built:
  - project setup
  - sign up / log in / log out
  - the proxy client (`send_chat`)
  - the model catalog: three models with provider and tier, a Models page, and on/off in the admin
  - billing accounts: personal accounts with 1,000 sign-up credits, shared accounts, admin credit grants, per-tier prices
  - chat sessions: pick a model and a billing account, chat with the full history sent each turn, a sidebar of your chats
  - metering: each turn is charged at its tier price, tokens and cost shown in the chat, sending blocked at a balance of 0 or less, a Usage page
  - the sidebar: rename and delete chats (delete hides the chat; its charges stay)
- All eight plans in the study's build order are done. Ideas for later are in TODO.md.
- The home page is the new chat page, in a Litechat-style layout: your chats on the left, the chat on the right.

Planned features are in [TODO.md](../../TODO.md). The full study is in `doc/study/1790660517_litechat-core.md`.

## Features

- [Configuration](features/configuration.md): settings and `.env`.
- [Auth](features/auth.md): sign up, log in, log out.
- [Proxy client](features/proxy-client.md): `send_chat()` and the `proxy_smoke` live check.
- [Model catalog](features/model-catalog.md): `LLMModel`, the Models page, turning models on and off.
- [Billing accounts](features/billing-accounts.md): accounts, credits (stored as micro-credits), ledger, balances, grants, tier prices.
- [Chat sessions](features/chat-sessions.md): new chat, the session page, the sidebar, the Send button script.
- [Metering](features/metering.md): charging each turn, blocking at 0, tokens and cost in the chat, the Usage page.
- [Sidebar](features/sidebar.md): rename and delete (hide) chats.

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
3. Set up the database. This also adds the three models to the catalog, the tier prices, and a billing account for any existing user.
   ```
   venv/bin/python manage.py migrate
   ```
4. Create an admin user. Run this in your own terminal, so the password stays out of any AI transcript:
   ```
   venv/bin/python manage.py createsuperuser
   ```
   Every new user, including this one, gets a personal billing account with 1,000 credits.
5. Start the server:
   ```
   venv/bin/python manage.py runserver
   ```
6. Open http://127.0.0.1:8000/. You are sent to the login page. Sign up, or log in.
7. Pick a model and a billing account, type a message, and click **Send**. This calls the real proxy, so the three `PROXY_*_API_KEY` values must be in `.env`. The runserver terminal prints one `proxy` line per call.
   Each reply is charged to the account you picked. Under the reply you see its tokens and cost. Click **Usage** in the header to see all your charges.
   To rename or delete a chat, click "⋯" next to it in the sidebar.
8. The admin is at http://127.0.0.1:8000/admin/.

## How to check it

```
venv/bin/python manage.py check
venv/bin/python manage.py test
```

Tests do not call the proxy and do not need real keys. They print some `proxy` log lines from fake replies. That is expected.

To check the real proxy (uses the network and your keys):

```
venv/bin/python manage.py proxy_smoke
```

## Known problems

See [footguns](footguns/):

- [Python HTTPS certificates on macOS](footguns/python-ssl-certificates-macos.md)
- [Proxy requests can hang](footguns/proxy-timeouts.md)
- [Django logout needs a POST](footguns/django-logout-requires-post.md)
- [Proxy log lines were not shown (fixed)](footguns/proxy-logs-not-shown.md)
- [Every user gets a billing account, and users can't be deleted](footguns/every-user-gets-a-billing-account.md)
- [The chat page waits for each reply](footguns/chat-waits-for-the-reply.md)
- [The balance can go below 0](footguns/balance-can-go-below-zero.md)
- [Anthropic's input_tokens leaves out cached tokens](footguns/anthropic-input-tokens-leave-out-cache.md)
- [Deleted chats are only hidden](footguns/deleted-chats-are-only-hidden.md)
