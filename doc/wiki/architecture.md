# Architecture

## Layout

```
manage.py
config/            Django project package
  settings.py      Settings. Loads .env.
  urls.py          URL routes
  tests.py         Project smoke tests
  asgi.py, wsgi.py Server entry points
requirements.txt   Pinned packages
.env.example       Names of the variables .env needs (no values)
doc/               Studies, plans, and this wiki
```

## Apps

No project apps yet. Only Django's built-in apps are installed:
`admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`.

Planned apps (from the study): `accounts`, `catalog`, `billing`, `chat`, and a `proxy` module.

## Models

No project models yet. The database has only Django's built-in tables (users, groups, permissions, sessions, admin log).

Database: SQLite at `db.sqlite3` in the repo root. It is git-ignored.

## URLs

| URL | What |
|---|---|
| `/admin/` | Django admin |

Any other URL returns 404. There is no home page yet.

## Templates

None yet. The admin uses Django's built-in templates.

## Settings

See [Configuration](features/configuration.md).
