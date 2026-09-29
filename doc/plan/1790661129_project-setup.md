# Plan: project setup

Based on: `doc/study/1790660517_litechat-core.md` (build order item 1, NOTEs in section 14).

Goal: an empty Django 5.2 project that loads `.env`, passes `manage.py check`, and has a working admin.
No app features yet. Auth is the next plan.

Branch: `feat/project-setup`, made from `main`.

## Decisions made in this plan

- The Django project package is named `config` (so we get `config/settings.py`, `config/urls.py`). This keeps it apart from the apps we add later.
- `python-dotenv` loads `.env` from the repo root at the top of `settings.py`. It does not overwrite variables already set in the shell.
- `DJANGO_SECRET_KEY` is required. If it is missing, settings raise a clear error.
- `DJANGO_DEBUG` is optional and defaults to on. This is a local dev app. Deployment is out of scope. A deploy plan must change this.
- The proxy keys are optional at startup. Settings put them in `PROXY_KEYS = {"openai": ..., "anthropic": ..., "google": ...}`, with `""` when missing. Code that calls the proxy will raise a clear error later. So `check` and tests run without keys.
- Add `.env.example` with variable names only, no values. It shows what `.env` needs.
- `requirements.txt` pins exact versions from `pip freeze` (Django, python-dotenv, and Django's own dependencies `asgiref` and `sqlparse`).

## Steps

- [x] **1. Ignore Claude Code local settings**
  - Files: `.gitignore` (add `.claude/settings.local.json`).
  - Test: `git check-ignore -v .claude/settings.local.json` prints the `.gitignore` rule.
  - Commit: `chore: ignore Claude Code local settings`

- [x] **2. Install Django 5.2.x and python-dotenv**
  - Files: `requirements.txt` (new).
  - Do: `venv/bin/pip install "Django>=5.2,<5.3" python-dotenv`, then `venv/bin/pip freeze > requirements.txt`.
  - Test: `venv/bin/python -m django --version` prints `5.2.x`. `venv/bin/pip install -r requirements.txt` reports nothing new to install.
  - Commit: `build: add Django 5.2 and python-dotenv`

- [x] **3. Start the Django project**
  - Files: `manage.py`, `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/asgi.py`, `config/wsgi.py` (all new, from `venv/bin/django-admin startproject config .`).
  - Test: `venv/bin/python manage.py check` reports no issues. `venv/bin/python manage.py migrate` runs (creates `db.sqlite3`, which is already git-ignored).
  - Note: the generated `settings.py` has a hardcoded `SECRET_KEY`. It is replaced in step 4. It is a throwaway dev value, not a real secret, but step 4 must land before anything is pushed.
  - Commit: `chore: start Django project`

- [x] **4. Load settings from .env**
  - Files: `config/settings.py`, `.env.example` (new).
  - Do:
    - `load_dotenv(BASE_DIR / ".env")` at the top of settings.
    - `SECRET_KEY` from `DJANGO_SECRET_KEY`. Raise `ImproperlyConfigured` with a clear message if missing.
    - `DEBUG` from `DJANGO_DEBUG` (default on). `ALLOWED_HOSTS` from `DJANGO_ALLOWED_HOSTS` (comma list, default `localhost,127.0.0.1`).
    - `PROXY_BASE_URL = "https://proxy.litechat.ai"` and `PROXY_KEYS` from `PROXY_OPENAI_API_KEY`, `PROXY_ANTHROPIC_API_KEY`, `PROXY_GOOGLE_API_KEY`.
    - Remove the generated hardcoded `SECRET_KEY`.
    - `.env.example` lists `DJANGO_SECRET_KEY=`, `DJANGO_DEBUG=`, `DJANGO_ALLOWED_HOSTS=`, and the three proxy key names, all empty.
  - Test (never prints values, only True/False):
    - `venv/bin/python manage.py check` passes.
    - `env -u PROXY_OPENAI_API_KEY -u PROXY_ANTHROPIC_API_KEY -u PROXY_GOOGLE_API_KEY venv/bin/python manage.py shell -c "from django.conf import settings; print({k: bool(v) for k, v in settings.PROXY_KEYS.items()})"` prints all `True`. This proves the keys come from `.env`, not the shell.
    - `grep -n SECRET_KEY config/settings.py` shows no literal key.
  - Commit: `feat: load settings and proxy keys from .env`

- [x] **5. Add smoke tests**
  - Files: `config/tests.py` (new).
  - Tests:
    - The admin login page (`/admin/login/`) returns 200.
    - `settings.PROXY_KEYS` has exactly the keys `openai`, `anthropic`, `google`.
    - The tests do not check key values and do not call the proxy.
  - Test: `venv/bin/python manage.py test` passes.
  - Commit: `test: add project setup smoke tests`

## Done when

- `venv/bin/python manage.py check` and `venv/bin/python manage.py test` pass.
- `venv/bin/python manage.py migrate` has nothing left to apply.
- No key or secret value appears in any tracked file.

## At rendezvous (human does this)

1. Create an admin user in your own zsh terminal, not inside Claude Code (so the password stays out of the transcript): `cd /Users/chessietrillana/litechat-clone && venv/bin/python manage.py createsuperuser`.
2. Start the server: `venv/bin/python manage.py runserver`.
3. Open http://127.0.0.1:8000/admin/ and log in. You should see the Django admin with "Groups" and "Users".
4. Open http://127.0.0.1:8000/. You should see a yellow Django "Page not found (404)" page that lists `admin/`. That is expected: there is no home page yet. Auth adds one next.
