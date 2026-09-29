# Model catalog

The app keeps a list of LLMs users can pick. Each model has a provider and a tier.
Admins can turn models on and off. Logged-in users see the list on the **Models** page.

Plan: `doc/plan/1790663929_model-catalog.md`. Decisions: study NOTEs Q1–Q4.

## The models

Only the three models the proxy offers are listed (NOTE Q1). They are shown as the providers name them (NOTE Q3).

| Display name | Provider | Proxy model ID | Tier |
|---|---|---|---|
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | Value |
| Claude Haiku 4.5 | Anthropic | `claude-haiku-4-5-20251001` | Standard |
| GPT-5.6 Luna | OpenAI | `gpt-5.6-luna` | Premium |

All three are really the same model (DeepSeek Flash) behind the proxy. See the study, section 3. Users are not told this (NOTE Q3).

A data migration (`catalog/migrations/0002_seed_proxy_models.py`) adds these rows.

- It only adds missing rows. It never changes or deletes existing ones.
- So running it again does not undo admin edits.

## The `LLMModel` table

| Field | Meaning |
|---|---|
| `display_name` | What users see |
| `provider` | `openai`, `anthropic`, or `google` (shown as OpenAI, Anthropic, Google). **Also the proxy interface** passed to `send_chat`. |
| `proxy_model_id` | The ID sent to the proxy. Unique. |
| `tier` | 1 Value, 2 Standard, 3 Premium. Stored as a number so it sorts in tier order. |
| `is_active` | Off = hidden from users |
| `created_at`, `updated_at` | Timestamps |

- Default order: tier, then display name.
- `LLMModel.objects.active()` gives only active models. The new chat form uses it for the model picker.
- Turning a model off also stops sending in existing chats with it. Their messages still show.
- Prices are per tier, not per model: `TierPrice` in [Billing accounts](billing-accounts.md). Each turn is charged at its model's tier price. See [Metering](metering.md).

## Admin

Django admin → **Catalog** → **LLM models**.

- Tick or untick **Active** in the list, then click **Save**.
- Or select models and use the **Turn on selected models** / **Turn off selected models** action.
- Filter by provider, tier, or active. Search by name or proxy model ID.
- **Models cannot be deleted** in the admin. Turn them off instead. Chat sessions point at models, and protect them from deletion.
- To add a model, click **Add LLM model**. Its provider must match one of the three proxy interfaces.

## Models page

- URL: `/models/` (name `models`). Login needed. Visitors are sent to the login page.
- A table of active models in tier order: Model, Provider, Tier.
- If no models are active, it says "No models are available right now."
- Linked from the nav bar (logged-in users) and the new chat page ("About the models").

## Tests

`catalog/tests.py`:

- `LLMModelTests`: name, order, `active()`, unique proxy ID, and that providers match the proxy interfaces and `PROXY_KEYS`.
- `LLMModelAdminTests`: list page loads, turn on/off actions, delete is blocked (page, action, button).
- `SeedTests`: the three seed rows are right, and seeding again changes nothing.
- `ModelsPageTests`: login needed, rows and order, hidden when off, empty message, nav and home links.

The seed rows exist in the test database too, so tests make their own rows or look up seed rows by ID.
