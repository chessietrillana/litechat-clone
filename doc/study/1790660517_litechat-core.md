# Study: Litechat clone core features and the proxy

Date: 2026-09-29

## 1. The request

Build a Litechat clone. Users get metered, pay-as-you-go access to LLMs from several providers. No upfront subscription.

Core features:

1. Users can sign up, log in, and log out.
2. Users start a chat session by picking a model and a billing account. Each turn sends the full history to the model.
3. Sessions are saved and listed in a sidebar. Users can rename, reopen, and delete them.
4. Usage is metered per session. Each session is charged to the billing account picked at the start.
5. Models are listed with their provider and a tier (Value, Standard, Premium).

Out of scope for now: real payments, streaming, file uploads, web search, Google login, deployment.

This study covers the proxy, the key setup, usage fields, loading `.env`, packages, a build order, and open questions.

## 2. Current state of the codebase

- No Django project yet. No apps, no `settings.py`, no `urls.py`.
- The venv has Python 3.11.5 with only `pip` and `setuptools`. Django is **not installed**.
- There is no `requirements.txt` yet.
- `.gitignore` already ignores `.env`, `venv/`, and `db.sqlite3`.
- `TODO.md` is empty.
- Docs folders exist: `doc/study/`, `doc/plan/`, `doc/wiki/footguns/`.

### Key names: a mismatch

The request names the keys `PROXY_OPENAI_KEY`, `PROXY_ANTHROPIC_KEY`, `PROXY_GOOGLE_KEY`.
Those are **not set** in the shell.

The keys that are set are the names in CLAUDE.md:

- `PROXY_OPENAI_API_KEY`
- `PROXY_ANTHROPIC_API_KEY`
- `PROXY_GOOGLE_API_KEY`

(The last commit renamed them to avoid a clash with Claude Code.) This study and all code will use the `_API_KEY` names.
The proxy docs use a third set of names in examples (`BUILD_OPENAI_KEY` and so on). Ignore those.

I checked only whether each name is set. I did not read `.env` or print any key.

## 3. The proxy

Docs: https://proxy.litechat.ai/docs. The service calls itself "BUILD LLM Proxy".

### Interfaces

| Interface | Endpoint | Auth header | Model named in docs |
|---|---|---|---|
| OpenAI Chat Completions | `POST /openai/v1/chat/completions` | `Authorization: Bearer <key>` | `gpt-5.6-luna` |
| OpenAI Responses | `POST /openai/v1/responses` | `Authorization: Bearer <key>` | `gpt-5.6-luna` |
| Anthropic Messages | `POST /anthropic/v1/messages` (also needs `anthropic-version: 2023-06-01`) | `x-api-key: <key>` | `claude-haiku-4-5-20251001` |
| Google Gemini | `POST /google/v1beta/models/<model>:generateContent` | `x-goog-api-key: <key>` | `gemini-3.8-flash` |

The model goes in the request body for OpenAI and Anthropic. For Google, it goes in the URL.

### Big surprise: one real model behind everything

The docs say: "BUILD LLM Proxy uses DeepSeek Flash for all three provider interfaces. The interfaces do not reproduce the named providers' model behavior."

So "GPT", "Claude", and "Gemini" here are the same model with different API shapes.
The token counts below match across all three interfaces, which fits this.
This matters for tiers and pricing. See open questions.

### Other doc points that matter to us

- The app must keep the history and send it every turn. The proxy stores nothing (`store: false`; `previous_response_id` is not supported).
- Check the finish reason before treating an answer as complete.
  - OpenAI: `finish_reason` = `stop` (ok), `length` (cut off), `tool_calls`.
  - Anthropic: `stop_reason` = `end_turn` (ok), `max_tokens` (cut off), `tool_use`.
  - Google: `finishReason` = `STOP` (ok), `MAX_TOKENS` (cut off), `SAFETY` (filtered).
- Errors: 400 bad request. 401/403 bad key. 429 too many requests. 502/504 upstream failed. 503 contact admin.
- "Do not automatically retry after partial output arrives. Usage can be unknown after a failure."
- Reasoning/thinking can be turned off: OpenAI `reasoning_effort: "none"`, Anthropic `thinking: {"type": "disabled"}`, Google `thinkingConfig.thinkingBudget: 0`.
- System prompts: OpenAI uses a `system` message. Anthropic uses a top-level `system` field. Google uses `systemInstruction`.
- Google uses role `model`, not `assistant`, and text sits in `parts`.

## 4. Which key works with which interface

Tested with curl. One request per cell, 30 second timeout. Keys were passed to curl through stdin, so they never appeared on the command line or in output.

| Interface ↓ / Key → | OpenAI key | Anthropic key | Google key |
|---|---|---|---|
| OpenAI Chat Completions | **200** | 401 | 401 |
| Anthropic Messages | 401 | **200** | 401 |
| Google Gemini | 401 | 401 | **200** |

Each key works only with its own interface. A wrong key gets 401 `invalid or inactive provider key`.
Some cells timed out on the first try and passed on a retry. See section 7.

The 401 error bodies follow each provider's own shape:

- OpenAI: `{"error": {"code": "Unauthorized", "message": "...", "param": null, "type": "authentication_error"}}`
- Anthropic: `{"type": "error", "error": {"message": "...", "type": "authentication_error"}}`
- Google: `{"error": {"code": 401, "message": "...", "status": "UNAUTHORIZED"}}`

## 5. Usage and token fields

Redacted sample responses are saved in `doc/study/1790660517_proxy-samples/`:

- `openai_single.json`, `openai_multiturn.json`
- `anthropic_single.json`, `anthropic_multiturn.json`
- `google_multiturn.json` (the single-turn Google request timed out, so there is no single-turn file. The shape is the same.)

I checked each file. None contains a key value. Response IDs are random UUIDs and are safe to keep.

### Fields per interface

| Meaning | OpenAI (`usage`) | Anthropic (`usage`) | Google (`usageMetadata`) |
|---|---|---|---|
| Input tokens | `prompt_tokens` | `input_tokens` | `promptTokenCount` |
| Output tokens | `completion_tokens` | `output_tokens` | `candidatesTokenCount` |
| Total | `total_tokens` | (none. Add them up) | `totalTokenCount` |
| Cached input | `prompt_cache_hit_tokens`, `prompt_tokens_details.cached_tokens` | `cache_read_input_tokens` | `cachedContentTokenCount` |
| Other | `prompt_cache_miss_tokens` | `cache_creation_input_tokens`, `service_tier` | — |

For metering we only need input and output tokens. We should also store cached tokens in case pricing uses them later.
All cached counts were 0 in our tests.

Where the answer text is:

- OpenAI: `choices[0].message.content`
- Anthropic: every `content[]` block with `type == "text"`, joined
- Google: every `candidates[0].content.parts[].text`, joined

### Hidden token overhead (~170 tokens per request)

The prompt "Say hello in one sentence." is about 7 tokens. The proxy reported **183 input tokens**. This was the same on all three interfaces.
The multi-turn test (3 short messages) reported 203.

So each request carries about 170–175 extra input tokens we did not send. It is likely a hidden system prompt added by the proxy.
The model also calls itself "GPT" or "Gemini" depending on the interface, which fits a hidden system prompt.

Effect: every turn costs at least ~170 input tokens, even for "hi". We need to decide whether users pay for this (see open questions).

## 6. Loading `.env` into Django

Right now the keys are exported in the shell that runs Claude Code. A server started from another terminal may not have them.

Options:

1. **`python-dotenv` (recommended).** Call `load_dotenv(BASE_DIR / ".env")` at the top of `settings.py`. Then read `os.environ["PROXY_OPENAI_API_KEY"]` and so on. It does not overwrite variables that are already set. It is small and has no dependencies.
2. **`django-environ`.** More features (typed values, DB URLs). More than we need.
3. **Hand-written parser.** About 10 lines of stdlib code. No package. But we must handle quotes and comments ourselves.

Either way:

- Settings read the keys into e.g. `PROXY_KEYS = {"openai": ..., "anthropic": ..., "google": ...}`.
- A missing key should raise a clear error when a chat is sent, not when the server starts. That way `manage.py check` and tests still run without keys.
- `SECRET_KEY` and `DEBUG` should also come from `.env`. The human would need to add `DJANGO_SECRET_KEY` to `.env`.

## 7. Footguns found during this study

Recorded in `doc/wiki/footguns/`:

- **`python-ssl-certificates-macos.md`**: python.org Python on macOS could not verify HTTPS certificates until "Install Certificates.command" was run. The human ran it. Python HTTPS to the proxy now works.
- **`proxy-timeouts.md`**: about 5 of 18 requests hung until the 30 second timeout. The same request passed on retry. An earlier probe with 90 second timeouts and 3 retries hung for over 5 minutes. Rule: always set a timeout, and do not auto-retry.

## 8. Packages we need

| Package | Why | Status |
|---|---|---|
| `Django` 5.2.x (latest 5.x, LTS) | The app | Needed. Not installed. |
| `python-dotenv` | Load `.env` | Recommended. Needs approval. |

Not needed:

- **Provider SDKs** (`openai`, `anthropic`, `google-genai`). The request shapes are simple JSON. Three SDKs add many dependencies. We only need a small part of each API.
- **`requests` / `httpx`.** Stdlib `urllib.request` is enough for plain JSON POSTs with a timeout. It is easy to mock in tests. We can switch later if streaming comes into scope.

## 9. Design sketch (for the plan, not final)

Apps:

- `accounts`: sign up, log in, log out. Uses Django built-in auth views and `UserCreationForm`.
- `catalog`: `Model` table with display name, provider (OpenAI / Anthropic / Google), proxy model ID, tier, prices, active flag. Managed in the admin.
- `billing`: `BillingAccount` and a ledger of credit and charge entries.
- `chat`: `ChatSession` (user, model, billing account, title, timestamps) and `Message` (role, content, token counts, cost).
- `proxy` (plain module): one adapter per interface. Each adapter takes a history list and returns `(text, input_tokens, output_tokens, cached_tokens, finish_reason, raw_id)`. Views never touch provider JSON.

Money: store as integers in a small unit (for example micro-credits), never floats.
Charge: after each successful reply, in one DB transaction, save the assistant message and add a charge entry to the ledger.
Keep charge records even after a session is deleted.

## 10. Build order

Each item is one plan. Most plans will take several commits.

1. **Project setup.** Install Django and python-dotenv, start the project, load `.env`, add `requirements.txt`. Check with `manage.py check`.
2. **Auth.** Sign up, log in, log out, a base template, and a login-required home page.
3. **Model catalog.** `Model` table with provider and tier, admin, seed data, and a models page.
4. **Proxy client.** The three adapters with timeouts and error handling. Unit tests use saved sample JSON (no network). Plus one manual management command for a live smoke test.
5. **Billing accounts.** Accounts, ledger, balance, admin credit grants.
6. **Chat sessions.** New session (pick model and account), chat page, send full history, save messages.
7. **Metering.** Charge per turn, show usage and cost per session, block when the balance is too low.
8. **Sidebar.** List sessions, rename, reopen, delete.

Items 6 and 7 can merge if billing is simple. Items 5–7 depend on the billing answers below.

## 11. What was not tested

- OpenAI Responses endpoint (`/openai/v1/responses`). We plan to use Chat Completions only.
- Model list endpoints (`/openai/v1/models`, `/anthropic/v1/models`, `/google/v1beta/models`).
- Model names other than the three in the docs. We do not know if the proxy accepts e.g. `gpt-4o` or rejects it.
- Error bodies for 400, 429, 502, 503, 504.
- Usage on a truncated reply (`max_tokens` reached).
- Whether a `system` prompt we send changes the ~170 token overhead.
- Rate limits and how many requests can run at once.
- Streaming (out of scope).
- A single-turn Google sample (timed out. Multi-turn sample was captured).
- The proxy `/admin` page. We have no access and did not try.

## 12. Recommendation

- Build on Django 5.2 with `python-dotenv` and stdlib `urllib`. No SDKs.
- Use Chat Completions, Messages, and generateContent. One adapter each.
- Keep models in an admin-editable table, so the human can add names, tiers, and prices without code changes.
- Use a ledger for billing. Balance = credits − charges. Admins grant credits in the Django admin until real payments exist.
- Set a 30 second timeout on every proxy call. No auto-retry. Do not charge when the proxy returned no usage.
- Start with plans 1 and 2 now. They do not depend on the open questions.

## 13. Open questions for the human

### Models and tiers

1. The proxy has one real model (DeepSeek Flash) and names only three model IDs. Which models should the app list? Just the three? Or more display names that map to the same three IDs?
2. How are tiers assigned? For example: is `gemini-3.8-flash` Value, `claude-haiku-4-5` Standard, `gpt-5.6-luna` Premium? Or should each tier be a separate list entry?
3. Should the app tell users that all models are the same underlying model? Or show them as the providers name them?
4. Should admins be able to turn models on and off in the admin? (Recommended: yes.)

### Pricing

5. How is a turn priced? Per input token and per output token, per model (recommended)? Or a flat price per message? Or per tier?
6. What are the actual prices? For example, credits per 1M input tokens and per 1M output tokens for each tier.
7. Is there a markup over our cost? Do we know what the proxy costs us?
8. Do users pay for the ~170 hidden overhead tokens? (Simplest: yes, charge what the proxy reports.)
9. Are cached input tokens cheaper?
10. If prices change, old charges keep their old price. OK? (Recommended: yes. Store the price used on each charge.)

### Credits and balances

11. What unit do users see: dollars, or "credits"? If credits, what is 1 credit worth?
12. Do new users get free starting credits? How many?
13. With no real payments, how do balances go up? Admin grants in the Django admin (recommended)? A fake "top up" button?
14. What happens when a balance is too low? Block before sending? Allow one last turn and go negative? Allow a small negative limit?
15. We cannot know the cost of a turn before it runs. Should we block when the balance is below some minimum?
16. Do we charge for failed or cut-off replies? (Recommended: charge only when the proxy returns usage.)

### Billing accounts

17. What kinds of billing accounts exist? Ideas:
    - Personal: one per user, made at sign-up.
    - Shared/team: several users charge one account, with an owner.
    - Admin-granted: e.g. a class or a promo account.
18. Can one user have several accounts? Who can create them?
19. For shared accounts: how are members added? Can the owner see each member's usage? Can there be spending limits per member?
20. Can a session's billing account or model be changed after it starts? (Recommended: no, fixed at start, as the request implies.)

### Sessions and chat

21. When a session is deleted, is it gone for good, or hidden? Its charges stay in the ledger either way. OK?
22. Long chats get more expensive each turn, because the full history is sent. Should we cap history length or warn users?
23. What should the default session title be? The first words of the first message? "New chat" + date?
24. Should we set a max reply length (`max_tokens`)? What value? It affects cost and cut-off replies.
25. Should thinking/reasoning be off (cheaper, faster) or on? (Recommended: off for now.)
26. Is there a system prompt we want to send?

### Accounts and auth

27. Sign up with username, or email, or both? Email verification needed? (Recommended: username + password, no email for now.)
28. Should users see a usage/billing page with their history of charges?

### Setup

29. Approve installing `Django` 5.2.x and `python-dotenv`?
30. Please add `DJANGO_SECRET_KEY` to `.env` when we start plan 1. (I will not read or write `.env`.)
