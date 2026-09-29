# Billing accounts

Every user has a personal billing account with free credits. Admins can make shared accounts, add members, and grant credits.
Each account's balance comes from a ledger. Per-tier token prices are set in the admin.

Charging per chat turn, blocking at 0, and the usage page are **not built yet**. They come in the metering plan (plan 7).

Plan: `doc/plan/1790664853_billing-accounts.md`. Decisions: study NOTEs Q5–Q13 and Q17–Q20.

## Credits and micro-credits

- Users and admins see **credits** (NOTE Q11).
- The database stores **micro-credits (µc)** as whole numbers: **1 credit = 1,000,000 µc**. Fields that hold µc end in `_micro`.
- Why: with prices of up to 3 decimals per 1K tokens, every per-token price is a whole number of µc. So `cost = tokens × µc per token` is exact. There is no rounding and there are no floats.
- `billing/units.py` does all conversion:
  - `credits_to_micro(Decimal)` refuses floats and more than 6 decimals.
  - `micro_to_credits(int) -> Decimal`
  - `format_credits(int)` gives `1,000`, `999.817`, or `0.000183`.
- In templates: `{% load billing %}` then `{{ amount_micro|credits }}`.

## Accounts

| Kind | Made by | Who can bill to it |
|---|---|---|
| Personal | Automatically, one per user | The owner |
| Shared | Admins only (NOTE Q17) | Its members, added by admins (NOTE Q19) |

- `BillingAccount.objects.for_user(user)` gives the accounts a user may bill to: their personal account plus the shared ones they belong to (NOTE Q18). Chat will use it for the account picker.
- Database rules:
  - A personal account has an owner, and a shared one has none.
  - A shared account has a name.
  - A user has at most one personal account.
- Accounts cannot be deleted.

## Ledger and balance

- `LedgerEntry`: account, `amount_micro` (signed), kind, note, `created_by`, `created_at`.
- Kinds: `signup_grant` and `admin_grant`. Plan 7 will add `charge`, with negative amounts.
- **Balance = the sum of the account's entries.** It is computed each time, not stored, so it can't drift from the ledger.
  - `account.balance_micro()` for one account.
  - `BillingAccount.objects.with_balance()` adds `balance` to each row. It uses a subquery, so filtering by members never counts an entry twice.
- Entries are never changed or deleted.

## Sign-up credits

- Every new user gets a personal account and a **1,000-credit** `signup_grant` (NOTE Q12), through a `post_save` signal in `billing/signals.py`.
- The amount is the setting `BILLING_SIGNUP_GRANT_CREDITS` (1000).
- It runs for the sign-up page, `createsuperuser`, and the admin. See [the footgun](../footguns/every-user-gets-a-billing-account.md).
- Users made before billing existed got the same account and grant from migration `0004_backfill_personal_accounts`.

## Users can't be deleted

A user's personal account has ledger entries, and entries are protected. So deleting a user fails with `ProtectedError`, and nothing is removed.
To lock someone out, untick **Active** on the user in the admin.

## Tier prices

- `TierPrice`: one row per tier, `price_per_1k_tokens` in credits (up to 3 decimals, not negative).
- Seeded (NOTE Q6): **Value 1, Standard 3, Premium 10** credits per 1K tokens.
- One price for input, output, and cached tokens (NOTE Q5, Q9). No markup (NOTE Q7).
- `micro_per_token` gives the exact µc per token (Value 1 → 1,000 µc).

## Admin

Django admin → **Billing**:

- **Billing accounts**
  - The list shows account, kind, owner, number of members, and balance. Filter by kind, search by name or owner.
  - **Add** makes a shared account: name (required) and members.
  - Personal accounts: kind and owner are read-only, and there is no members picker.
  - Each account page shows its ledger entries (read-only) and a **Grant credits** link.
  - No delete.
- **Ledger entries**
  - **Add** is the **Grant credits** form: account, amount in credits (more than 0, up to 6 decimals), note. It records the admin who granted it.
  - Existing entries are view-only.
- **Tier prices**
  - Edit the price right in the list and click **Save**. No add or delete.

Only staff can use the admin. Users cannot grant themselves credits (NOTE Q13).

## Home page

"Your billing accounts" lists each account the user can bill to, with its balance, e.g. "alice (personal): 1,000 credits".

## Tests

All in `billing/tests/`, plus `config/tests.py`:

- `test_units.py`: conversion, refusing floats, formatting, the template filter.
- `test_models.py`: database rules, `for_user`, balance and `with_balance`, names.
- `test_prices.py`: seeded prices, `micro_per_token`, reseeding keeps admin changes, the price admin.
- `test_signup_grant.py`:
  - account and grant for each way a user is made
  - the setting
  - user deletion is blocked
  - the backfill
- `test_admin.py`: account list, shared account add and name rule, locked personal accounts, no delete, grant form, bad amounts, read-only entries, non-staff refused.
- `config/tests.py` `HomeBillingAccountsTests`: the home page shows the right accounts and balances.
