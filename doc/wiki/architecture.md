# Architecture

## Layout

```
manage.py
config/                 Django project package
  settings.py           Settings. Loads .env.
  urls.py               Root URL routes
  views.py              home view
  tests.py              Project and home page tests
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
templates/              Shared templates
  base.html             Page shell and nav bar
  home.html             Home page
static/css/site.css     Plain site styles
requirements.txt        Pinned packages
.env.example            Names of the variables .env needs (no values)
doc/                    Studies, plans, and this wiki
```

## Apps

| App | What it does |
|---|---|
| `accounts` | Sign up, log in, log out. No models. Uses Django's built-in `User`. |
| `proxy` | `send_chat()` sends a chat history to the proxy and returns text and token usage. No models, no URLs. Has the `proxy_smoke` command. See [Proxy client](features/proxy-client.md). |

Django built-in apps: `admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`.

Planned apps (from the study): `catalog`, `billing`, `chat`.

## Management commands

| Command | What |
|---|---|
| `proxy_smoke [--interface X] [--prompt "..."]` | Sends one live request per proxy interface and prints the result. Uses real keys and the network. |

## Models

No project models yet. Users are Django's built-in `django.contrib.auth.models.User`.
We chose not to use a custom user model. Billing data will live in its own models.

Database: SQLite at `db.sqlite3` in the repo root. It is git-ignored.

## URLs

| URL | Name | View | Login needed |
|---|---|---|---|
| `/` | `home` | `config.views.home` | Yes |
| `/accounts/signup/` | `signup` | `accounts.views.SignUpView` | No (logged-in users go home) |
| `/accounts/login/` | `login` | Django `LoginView` | No (logged-in users go home) |
| `/accounts/logout/` | `logout` | Django `LogoutView` (POST only) | — |
| `/admin/` | — | Django admin | Staff only |

## Templates

- `templates/base.html`: every page extends this. It has the nav bar and shows Django messages.
  - Visitors see **Log in** and **Sign up** links.
  - Logged-in users see their username and a **Log out** button (a POST form).
- `templates/home.html`: "Hello, <username>."
- `accounts/templates/registration/login.html`: the login form. Django's `LoginView` finds it by this path.
- `accounts/templates/accounts/signup.html`: the sign-up form, with password rules shown.

Styles: `static/css/site.css`. Plain CSS, no framework.

## Settings

See [Configuration](features/configuration.md).
