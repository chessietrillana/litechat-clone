# Architecture

## Layout

```
manage.py
config/                 Django project package
  settings.py           Settings. Loads .env.
  urls.py               Root URL routes
  tests.py              Project setup and logging tests
  asgi.py, wsgi.py      Server entry points
accounts/               App: sign up, log in, log out
  urls.py               signup, login, logout
  views.py              SignUpView
  tests.py              Login, logout, and sign-up tests
  templates/
    registration/login.html
    accounts/signup.html
proxy/                  App: talks to the LLM proxy (no models, no URLs)
  types.py              Message, ChatResult
  errors.py             ProxyError and subclasses
  transport.py          The only HTTP code (urllib, 30 s timeout, no retry)
  adapters/             openai.py, anthropic.py, google.py
  client.py             send_chat()
  management/commands/proxy_smoke.py   Live check command
  tests/                Tests and fixtures/ (real and synthetic proxy replies)
catalog/                App: the list of LLMs users can pick
  models.py             LLMModel, Provider, Tier
  admin.py              LLMModelAdmin (turn on/off, no delete)
  migrations/0002_seed_proxy_models.py   Seeds the three proxy models
  views.py, urls.py     Models page
  templates/catalog/model_list.html
  tests.py
billing/                App: billing accounts, ledger, tier prices
  units.py              Credits <-> micro-credits (µc), formatting
  models.py             BillingAccount, LedgerEntry, TierPrice
  signals.py            New user -> personal account + sign-up grant
  forms.py              Admin forms (shared account, grant credits)
  admin.py              Accounts, grants, tier prices
  templatetags/billing.py   {{ amount_micro|credits }}
  migrations/0003_seed_tier_prices.py, 0004_backfill_personal_accounts.py
  tests/
chat/                   App: chat sessions, the home page, the sidebar
  models.py             ChatSession, ChatMessage, make_title
  services.py           start_session, send_turn (the only chat code that calls the proxy)
  forms.py              NewChatForm, MessageForm
  views.py, urls.py     home, new_chat, session_detail
  admin.py              View-only chat sessions
  templates/chat/       layout.html (sidebar), new.html, session.html
  tests/
templates/              Shared templates
  base.html             Page shell and nav bar
  _messages.html        Django messages list
static/css/site.css     Plain site styles, chat layout and bubbles
static/js/chat.js       Send button script (plain JS)
requirements.txt        Pinned packages
.env.example            Names of the variables .env needs (no values)
doc/                    Studies, plans, and this wiki
```

## Apps

| App | What it does |
|---|---|
| `accounts` | Sign up, log in, log out. No models. Uses Django's built-in `User`. |
| `proxy` | `send_chat()` sends a chat history to the proxy and returns text and token usage. No models, no URLs. Has the `proxy_smoke` command. See [Proxy client](features/proxy-client.md). |
| `catalog` | `LLMModel`: the models users can pick, with provider and tier. Admin can turn them on and off. Models page. See [Model catalog](features/model-catalog.md). |
| `billing` | Personal and shared billing accounts, the credit ledger, balances, sign-up credits, admin grants, per-tier prices. See [Billing accounts](features/billing-accounts.md). |
| `chat` | Chat sessions and messages, the new chat (home) page, the session page, the sidebar. See [Chat sessions](features/chat-sessions.md). |

Django built-in apps: `admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`.

## Management commands

| Command | What |
|---|---|
| `proxy_smoke [--interface X] [--prompt "..."]` | Sends one live request per proxy interface and prints the result. Uses real keys and the network. |

## Models

| Model | App | What |
|---|---|---|
| `LLMModel` | `catalog` | One LLM: display name, provider (= proxy interface), proxy model ID (unique), tier, active flag, timestamps. Default order: tier, then name. |
| `BillingAccount` | `billing` | `kind` personal or shared, `name` (shared), `owner` (personal, cascades), `members` (shared, many-to-many with User). One personal account per user. |
| `LedgerEntry` | `billing` | `account` (protected), `amount_micro` (signed µc), `kind` (`signup_grant`, `admin_grant`), `note`, `created_by` (protected), `created_at`. Never changed or deleted. Balance = sum. |
| `TierPrice` | `billing` | One row per `tier`: `price_per_1k_tokens` (credits, 3 decimals). Seeded 1 / 3 / 10. |
| `ChatSession` | `chat` | `user`, `llm_model` (protected), `billing_account` (protected), `title`, `created_at`, `updated_at` (last activity). Model and account fixed at start. |
| `ChatMessage` | `chat` | `session`, `role` (`user`/`assistant`), `content`; for replies: `input_tokens`, `output_tokens`, `cached_tokens`, `finish_reason`, `response_id`. `created_at`. |

Users are Django's built-in `django.contrib.auth.models.User`.
We chose not to use a custom user model. Billing data lives in the `billing` models.
Every user has a personal `BillingAccount`, whose ledger entries protect the user from deletion.

Database: SQLite at `db.sqlite3` in the repo root. It is git-ignored.

## URLs

| URL | Name | View | Login needed |
|---|---|---|---|
| `/` | `home` | `chat.views.home` (new chat page) | Yes |
| `/chat/new/` | `chat_new` | `chat.views.new_chat` (POST only) | Yes |
| `/chat/<id>/` | `chat_session` | `chat.views.session_detail` (GET shows, POST sends) | Yes, and only the owner (others get 404) |
| `/accounts/signup/` | `signup` | `accounts.views.SignUpView` | No (logged-in users go home) |
| `/accounts/login/` | `login` | Django `LoginView` | No (logged-in users go home) |
| `/accounts/logout/` | `logout` | Django `LogoutView` (POST only) | — |
| `/models/` | `models` | `catalog.views.model_list` | Yes |
| `/admin/` | — | Django admin | Staff only |

## Templates

- `templates/base.html`: every page extends this. It has the nav bar.
  - Visitors see **Log in** and **Sign up** links.
  - Logged-in users see **Models**, their username, and a **Log out** button (a POST form).
  - Blocks: `content` (the narrow centered column, used by most pages), `main` (chat pages replace the whole column), `head`, `body_class`.
- `templates/_messages.html`: the Django messages list. Included by `base.html` and the chat layout.
- `chat/templates/chat/layout.html`: the chat layout. Sidebar (**New chat**, the user's chats) on the left, the chat on the right. Loads `js/chat.js`.
- `chat/templates/chat/new.html`: the home page. "Hello, <username>." and the new chat form (model, billing account with balance, message).
- `chat/templates/chat/session.html`: title, model and account, message bubbles, and the send box.
- `catalog/templates/catalog/model_list.html`: the models table, or an empty message.
- `accounts/templates/registration/login.html`: the login form. Django's `LoginView` finds it by this path.
- `accounts/templates/accounts/signup.html`: the sign-up form, with password rules shown.

Styles: `static/css/site.css`. Plain CSS, no framework.
Script: `static/js/chat.js`. Plain JS, chat pages only. The pages work without it.

## Settings

See [Configuration](features/configuration.md).
