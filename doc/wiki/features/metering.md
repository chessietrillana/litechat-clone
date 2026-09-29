# Metering

Every successful chat turn is charged to the session's billing account.
Users see the tokens and cost of each reply, the totals for each chat, and a **Usage** page with their charges.
Sending stops when an account's balance is 0 or less.

Plan: `doc/plan/1790667382_metering.md`. Decisions: study NOTEs Q5–Q10, Q14–Q16, Q28, and the human's review of the plan.

## How a turn is charged

- **Tokens** = input tokens + output tokens, as the proxy reports them (NOTE Q8). This includes the ~170 hidden tokens the proxy adds to every request.
  - If only one count is reported, the other counts as 0.
- **Cached tokens cost the same as normal input tokens** (NOTE Q9). On every interface, `input_tokens` already includes them. On Anthropic, the adapter adds the cache reads and writes. See [the footgun](../footguns/anthropic-input-tokens-leave-out-cache.md).
- **Price** = the tier price per 1K tokens from `TierPrice` (Value 1, Standard 3, Premium 10 credits, editable in the admin).
- **Cost (µc)** = tokens × µc per token. Always exact. No rounding, no floats.
  - Example: 183 in + 12 out on a Standard model = 195 × 3,000 µc = 0.585 credits.
- The price is read **before** the proxy call. An admin price edit during the wait does not change that turn.
- The price used is **copied onto the charge** (NOTE Q10). Later price changes don't touch old charges.

## When a turn is charged

| What the proxy did | Saved? | Charged? |
|---|---|---|
| Replied, with usage | Yes | Yes |
| Replied, with no usage | Yes | No (NOTE Q16). The reply shows "No usage reported · not charged". |
| Empty reply, with usage | Yes, with a note | Yes |
| Empty reply, no usage | No. The error shows, and the text stays in the box. | No |
| Timeout or error | No. The error shows, and the text stays in the box. | No |

- The user message, the reply, and the charge are saved **in one transaction**: all or nothing. The proxy call happens before it, outside the transaction.
- An empty reply that was charged is left out of later turns' history, with its question. The proxy refuses empty messages, and the history must go user, reply, user, reply.

## Blocking at 0

- Every send checks the account's balance **before** the proxy call (NOTE Q14–15). At 0 or less, it is refused: "This billing account has no credits left. Ask an admin to add credits, or start a new chat with another account."
- It applies to the new chat form and to sending in a chat.
- **A turn can take the balance below 0.** The cost is only known after the reply. The next send is then blocked. See [the footgun](../footguns/balance-can-go-below-zero.md).
- At 0 or less, the chat page shows a note in place of the input box. The server still checks every send.
- An admin grant that brings the balance above 0 lets sending start again.

## What users see

- **Chat page:**
  - Under each reply: "183 in · 12 out · 0.585 credits", or "No usage reported · not charged".
  - In the header: the account and its current balance, this chat's total tokens and cost, and a short note that one reply can take the balance below 0.
- **Usage page** (`/usage/`, **Usage** in the header, login needed, read only):
  - "Your billing accounts": each account the user can bill to, with its balance (it can be negative).
  - "Your charges": the user's own charges, newest first. Date, chat (linked), model, account, tokens (in / out), price per 1K, cost.
  - 50 rows per page, with **Newer** and **Older** links.
  - On a shared account, only your own charges are listed. Other members' use still shows in the balance.

## Data

- A charge is a `LedgerEntry` with `kind = charge` and a negative `amount_micro` (0 if the price is 0). So the balance is still the sum of the entries.
- Charge-only fields: `tokens` (billed) and `price_per_1k_tokens` (the price used). A database check makes charges have both and never add credits. Grants have neither.
- `created_by` is the user who sent the message.
- `ChatMessage.charge` links a reply to its charge (one-to-one, protected). Empty when nothing was charged.
- Charges are never changed or deleted. Deleting a chat or message keeps its charge.
- A user who made charges can't be deleted (`created_by` is protected). Untick **Active** instead.

## Admin

- **Billing → Ledger entries**: filter by kind **Charge**. The list and detail show tokens and price. Charges can't be added, changed, or deleted.
- **Billing → Billing accounts**: each account's entries include its charges.
- **Chat → Chat sessions**: each reply shows its cost.
- To give credits back after a negative balance, use **Grant credits** on the account.

## Code

| File | What |
|---|---|
| `billing/charges.py` | `record_charge(account, user, tokens, tier_price)` |
| `billing/models.py` | `LedgerEntry.Kind.CHARGE`, `tokens`, `price_per_1k_tokens`, `TierPrice.cost_micro` |
| `chat/services.py` | `check_can_send` (model, account, balance, price), `billed_tokens`, the transaction that saves and charges |
| `chat/models.py` | `ChatMessage.charge`, `cost_micro`, `is_empty_reply`, `history()` leaving out empty turns |
| `billing/views.py`, `billing/urls.py`, `billing/templates/billing/usage.html` | The Usage page |
| `billing/templatetags/billing.py` | Filters: `credits`, `thousands`, `negate`, `price` |
| `proxy/adapters/anthropic.py` | Adds cache tokens to `input_tokens` |

## Tests

- `billing/tests/test_charges.py`: cost math, `record_charge`, old charges keep their price, database checks, charge admin.
- `billing/tests/test_usage_page.py`: login, accounts and balances, charges and their order, other users' charges hidden, paging, nav link, query count.
- `chat/tests/test_charging.py`: charge per turn, each tier's price, missing usage, failures charge nothing, one transaction, price edits, missing price, shared accounts, Anthropic cache tokens end to end.
- `chat/tests/test_balance_block.py`: 0, below 0, 1 µc, going below 0 then blocked, grant unblocks, the page note, new chat.
- `chat/tests/test_usage_display.py`: per-reply line, header totals and balance, query count.
- `chat/tests/test_services.py`, `test_models.py`, `test_views.py`: empty replies with and without usage.
- `proxy/tests/test_anthropic.py`: cache reads and writes counted as input.
