# Plan: model catalog

Based on: `doc/study/1790660517_litechat-core.md` (build order item 3; section 9; NOTEs on Q1–Q4 and the `LLMModel` name).

Goal: the app knows which LLMs users can pick, with their provider and tier. Admins can turn models on and off.
Logged-in users see a **Models** page.

No prices in this plan. Pricing (Q5–Q10) is still open, so price fields come in the billing plan.

Branch: `feat/model-catalog`, made from `main`.

## Decisions made in this plan

- **New app `catalog`** with one model, `LLMModel` (NOTE: not "Model").
- **Fields:**

  | Field | Type | Notes |
  |---|---|---|
  | `display_name` | text, max 100 | What users see, e.g. "Claude Haiku 4.5" |
  | `provider` | choice: `openai` / `anthropic` / `google` | Shown as OpenAI / Anthropic / Google. Also picks the proxy interface: the values match the keys `send_chat` takes. |
  | `proxy_model_id` | text, max 100, **unique** | The ID sent to the proxy, e.g. `claude-haiku-4-5-20251001` |
  | `tier` | choice: 1 Value / 2 Standard / 3 Premium | Stored as a number so it sorts in tier order |
  | `is_active` | yes/no, default yes | Off = hidden from users (NOTE Q4) |
  | `created_at`, `updated_at` | timestamps | |

- **Default order:** tier (Value → Standard → Premium), then display name.
- **`LLMModel.objects.active()`** returns only active models. The models page uses it, and the chat plan will use it for the model picker.
- **Seed data** (NOTE Q1, Q2, Q3). A data migration adds exactly the three proxy models:

  | Display name | Provider | Proxy model ID | Tier |
  |---|---|---|---|
  | Gemini 3.8 Flash | Google | `gemini-3.8-flash` | Value |
  | Claude Haiku 4.5 | Anthropic | `claude-haiku-4-5-20251001` | Standard |
  | GPT-5.6 Luna | OpenAI | `gpt-5.6-luna` | Premium |

  - The display names are my best guess at "as the providers name them". You can change them in the admin at any time.
  - The migration uses `update_or_create` by `proxy_model_id`, so running it again is safe.
  - Undoing the migration does nothing. It never deletes rows.
- **Admin:**
  - The list shows name, provider, tier, proxy model ID, and active.
  - **Active can be ticked right in the list.** There are also "Turn on" and "Turn off" bulk actions.
  - Filters: provider, tier, active. Search: name and proxy model ID.
  - **Delete is turned off in the admin.** Chat sessions will point at models later, so the rule is "turn it off, don't delete it".
- **Models page:**
  - URL: `/models/`, name `models`. Login needed, like the rest of the site.
  - A table of active models only, in tier order. Columns: Model, Provider, Tier.
  - If there are no active models, it says so.
  - A **Models** link is added to the nav bar for logged-in users. The home page also links to it.
- **Tier shown as text only**, e.g. "Value". No badges or colors beyond a plain CSS class.
- **The `proxy_smoke` command is unchanged.** It keeps its own list of the three model IDs.
- **Tests do not assume the table is empty.** The seed migration runs in the test database too, so tests create their own rows with distinct IDs, or check the seed rows by ID.

## Steps

- [x] **1. `LLMModel` model and admin**
  - Files:
    - `catalog/` (new app, `venv/bin/python manage.py startapp catalog`). Add `"catalog"` to `INSTALLED_APPS`.
    - `catalog/models.py`: `Provider` (TextChoices), `Tier` (IntegerChoices), `LLMModelQuerySet.active()`, `LLMModel`, with `__str__` returning the display name.
    - `catalog/migrations/0001_initial.py` (from `makemigrations catalog`).
    - `catalog/admin.py`: `LLMModelAdmin`, set up as described above.
    - `catalog/tests.py`.
  - Tests:
    - `__str__` is the display name.
    - Default order is by tier, then name.
    - `active()` leaves out inactive models.
    - A duplicate `proxy_model_id` is rejected (`IntegrityError`).
    - Every `Provider` value is an interface `send_chat` knows (`proxy.client.ADAPTERS`), and so is every key in `settings.PROXY_KEYS`.
    - Admin (as a superuser):
      - The list page loads.
      - "Turn off" and "Turn on" change `is_active`.
      - Delete is not allowed: the delete page returns 403, and there is no delete action.
  - Check: `makemigrations --check --dry-run` reports no changes after the migration is made.
  - Commit: `feat: add LLMModel catalog model and admin`

- [x] **2. Seed the three proxy models**
  - Change during execution: the seed uses `get_or_create`, not `update_or_create`. If it ever runs again, it will not undo a name or on/off change made in the admin. A test checks this.
  - Files: `catalog/migrations/0002_seed_proxy_models.py` (hand-written `RunPython`, with a reverse that does nothing), `catalog/tests.py`.
  - Tests:
    - After migrations, the three seed rows exist with the provider, tier, display name, and active flag from the table above.
    - Running the seed function a second time leaves exactly three seed rows.
  - Check: `venv/bin/python manage.py migrate` applies it to your dev database. `showmigrations catalog` shows both migrations applied.
  - Commit: `feat: seed catalog with the three proxy models`

- [x] **3. Models page**
  - Files:
    - `catalog/views.py`: `model_list`, with `@login_required`.
    - `catalog/urls.py`: `path("", model_list, name="models")`.
    - `config/urls.py`: `path("models/", include("catalog.urls"))`.
    - `catalog/templates/catalog/model_list.html`.
    - `templates/base.html`: **Models** link in the nav for logged-in users.
    - `templates/home.html`: a link to the models page.
    - `static/css/site.css`: simple table styles.
    - `catalog/tests.py`.
  - Tests:
    - A visitor who is not logged in is sent to `/accounts/login/?next=/models/`.
    - A logged-in user gets 200 and sees the three seed models, with provider and tier text.
    - Rows are in the order Value, Standard, Premium.
    - A model that is turned off is not shown.
    - With every model turned off, the page shows the "no models" message.
    - The nav has a Models link when logged in, and none when logged out.
  - Commit: `feat: add models page`

## Done when

- `venv/bin/python manage.py check` and `venv/bin/python manage.py test` pass.
- `venv/bin/python manage.py makemigrations --check --dry-run` reports no changes.
- `venv/bin/python manage.py migrate` has nothing left to apply.

## At rendezvous (human does this)

Start the server in your own terminal: `venv/bin/python manage.py runserver`. Then:

1. Log in as `alice` (or any user). The nav bar now has **Models**. Click it.
2. You see three rows, in this order: **Gemini 3.8 Flash** (Google, Value), **Claude Haiku 4.5** (Anthropic, Standard), **GPT-5.6 Luna** (OpenAI, Premium).
3. Log out. Log in at http://127.0.0.1:8000/admin/ as your admin user. Click **LLM models** under **Catalog**.
4. Untick **Active** for GPT-5.6 Luna and click **Save** at the bottom of the list.
5. Log in as `alice` again and open **Models**. GPT-5.6 Luna is gone.
6. Back in the admin, tick GPT-5.6 Luna, choose the **Turn on** action, and click **Go**. It is back on the Models page.
7. In the admin, open a model. There is no **Delete** button.
