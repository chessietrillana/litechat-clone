# Plan: billing accounts

Based on: `doc/study/1790660517_litechat-core.md` (build order item 5; section 9; NOTEs on Q5–Q13 and Q17–Q20).

Goal:

- Every user has a personal billing account with 1,000 free credits.
- Admins can make shared accounts, add members, and grant credits.
- Each account has a balance, computed from a ledger.
- Per-tier token prices exist and can be edited in the admin.

**Not in this plan (plan 7, metering):** charging per turn, the price snapshot on each charge (Q10), blocking at balance ≤ 0 (Q14–15), no charge on failure (Q16), and the usage page (Q28).
This plan only builds what plan 7 will write into.

Branch: `feat/billing-accounts`. The plan file is committed on this branch, as asked, and not on `main`.

## Credit unit: micro-credits

All amounts are stored as **integers in micro-credits (µc)**. **1 credit = 1,000,000 µc.** Fields that hold µc end in `_micro`.

Why micro and not a bigger unit:

- Prices are per 1K tokens (Q6). At the Value price (1 credit per 1K tokens), one token costs **0.001 credit**. So the unit must be at most 1/1000 of a credit, just to charge one Value token.
- Milli-credits (1/1000) would be exact only while every price is a whole number of credits per 1K. An admin price like 1.5 or 0.25 credits per 1K would make per-token costs fractional again, so we would have to round.
- With micro-credits, any price with up to **3 decimals** (e.g. 0.001, 1.5, 12.345 credits per 1K) is a **whole number of µc per token**. Then `cost = tokens × µc_per_token` is always exact: no rounding, no floats.
- Size is no problem. `BigIntegerField` holds up to about 9.2 × 10¹⁸ µc, which is about 9.2 trillion credits.

People never see µc:

- Admins type prices and grants in **credits**, as decimals.
- Pages show credits with a thousands separator, trimming trailing zeros: `1,000`, `999.817`, `0.000183`.
- Conversion lives in one small module (`billing/units.py`) and uses `Decimal`, never `float`.

## Decisions made in this plan

- **New app `billing`.**
- **`BillingAccount`:**

  | Field | Notes |
  |---|---|
  | `kind` | `personal` or `shared` |
  | `name` | Required for shared. Blank for personal, which is shown as "alice (personal)". |
  | `owner` | The user, for personal accounts. Empty for shared. |
  | `members` | Users who may bill to a **shared** account (NOTE Q18, Q19). Not used for personal. |
  | `created_at` | |

  Database rules (constraints):

  - A personal account has an owner, and a shared one has none.
  - A user has at most one personal account.

- **Deleting a user is blocked when their personal account has ledger entries** (human's review):
  - `BillingAccount.owner` cascades, and `LedgerEntry.account` is protected. So deleting the user tries to delete their personal account, the account's entries block it, and Django raises `ProtectedError`. Nothing is deleted.
  - Every user gets a sign-up grant entry, so in practice **no user can be deleted**. To lock someone out, untick **Active** on the user in the admin.
  - `LedgerEntry.created_by` (the granting admin) is also protected, so the grant history stays complete.
  - Tested in step 3.
- **Who can bill to what (NOTE Q18):**
  - `BillingAccount.objects.for_user(user)` returns the user's personal account plus every shared account they are a member of.
  - Chat (plan 6) will use this for the account picker.
- **`LedgerEntry`, the ledger (NOTE: study section 12, "balance = credits − charges"):**

  | Field | Notes |
  |---|---|
  | `account` | The account. Entries are protected: an account with entries cannot be deleted. |
  | `amount_micro` | Signed integer. + adds credits. Plan 7's charges will be negative. |
  | `kind` | `signup_grant` or `admin_grant`. Plan 7 adds `charge` (a one-line migration). |
  | `note` | Free text, e.g. "Class promo" |
  | `created_by` | The admin who granted it. Empty for the automatic sign-up grant. |
  | `created_at` | |

  - Entries are **never edited or deleted**. The admin shows them read-only.
  - **Balance** is the sum of an account's entries. It is computed, not stored, so it can never drift from the ledger.
  - Helpers: `account.balance_micro()` and `BillingAccount.objects.with_balance()` (adds the balance to each row, for lists).
- **Per-tier prices (NOTE Q5, Q6, Q9):**
  - `TierPrice` has one row per tier.
    - `tier`: unique, and uses the catalog's `Tier` choices.
    - `price_per_1k_tokens`: a decimal in credits, up to 3 decimals. Must be ≥ 0.
  - Seeded Value 1, Standard 3, Premium 10.
  - One price for input, output, and cached tokens alike (Q5, Q9).
  - `micro_per_token` gives the exact integer µc per token (e.g. Value = 1,000 µc).
  - Prices live in `billing`, not `catalog`, because they belong to a tier, not to one model (Q5).
- **Sign-up grant (NOTE Q12, Q17):**
  - When a new `User` is saved for the first time, a `post_save` signal creates their personal account and a `signup_grant` of 1,000 credits, in one transaction.
  - The amount is a setting: `BILLING_SIGNUP_GRANT_CREDITS = 1000`.
  - This covers every way a user is made: the sign-up page, `createsuperuser`, and "Add user" in the admin. So admins get 1,000 credits too.
- **Existing users (alice, your admin user):**
  - A data migration gives each user who has no personal account one, plus the 1,000-credit sign-up grant, so they can chat later.
  - It skips users who already have an account, so running it again does nothing.
  - Undoing it deletes nothing.
- **Admin grants (NOTE Q13):**
  - Only admins (staff) can grant. There are no user-facing grant or top-up pages.
  - In the admin, **Ledger entries → Add** is the "grant credits" form. The fields are: account, amount in credits (> 0, up to 6 decimals), and note.
  - `kind` is set to `admin_grant`, and `created_by` to the logged-in admin.
  - Each account's page has a **Grant credits** link to this form, with the account filled in.
- **Admin for accounts:**
  - The list shows name, kind, owner, number of members, and balance. There is a filter by kind and a search by name or owner.
  - "Add" makes **shared** accounts only (NOTE Q17). Personal accounts are made automatically.
  - Shared accounts have a members picker (NOTE Q19). Personal accounts show no members picker, and their kind and owner cannot be changed.
  - The account page shows its ledger entries read-only.
  - **Accounts cannot be deleted**, the same rule as models. Sessions and charges will point at them.
- **Small user-facing piece:**
  - The home page lists "Your billing accounts" with each balance, e.g. "alice (personal): 1,000 credits".
  - This lets you check Q17–Q18 in the browser now.
  - This is the only page change. The full usage page is plan 7.
  - If you'd rather have no user-facing change in this plan, step 5 can be dropped.
- **Not added:**
  - a cached balance column (the sum is fast enough at this size; plan 7 can revisit)
  - negative admin adjustments (grants must be > 0)
  - owners or roles inside shared accounts (admins manage members)

## Steps

- [x] **1. Billing app: accounts, ledger, units**
  - Also added a database rule that a shared account needs a name. `with_balance()` uses a subquery, so filtering by members can't count an entry twice. A test covers this.
  - Files:
    - `billing/` (new app, `venv/bin/python manage.py startapp billing`). Add `"billing"` to `INSTALLED_APPS`.
    - `billing/units.py`:
      - `MICRO_PER_CREDIT = 1_000_000`
      - `credits_to_micro(Decimal)`: raises `ValueError` if the amount has more than 6 decimals
      - `micro_to_credits(int) -> Decimal`
      - `format_credits(int) -> str`
    - `billing/models.py`: `BillingAccount` (kinds, constraints, `for_user`, `with_balance`, `balance_micro`, `__str__`) and `LedgerEntry`.
    - `billing/templatetags/billing.py`: `{{ amount|credits }}` filter (uses `format_credits`).
    - `billing/migrations/0001_initial.py` (from `makemigrations`).
    - `billing/tests/` package: `test_units.py`, `test_models.py`. Remove the generated `billing/tests.py` stub, the same as we did for `proxy`. **This deletes a generated empty file. Please confirm.**
  - Tests:
    - `credits_to_micro`:
      - `Decimal("1")` → 1,000,000.
      - `Decimal("0.000001")` → 1.
      - `Decimal("0.0000001")` raises `ValueError`.
      - A float is refused (`TypeError`).
    - `format_credits`: 1,000,000,000 → `1,000`; 999,817,000 → `999.817`; 183 → `0.000183`; 0 → `0`; negative → `-1.5`.
    - Constraints:
      - A personal account without an owner fails.
      - A shared account with an owner fails.
      - A second personal account for the same user fails.
    - `for_user`: personal account plus shared accounts where the user is a member; not other people's personal accounts, and not shared accounts where the user is not a member.
    - Balance:
      - Is 0 with no entries.
      - Is the sum with several entries, including a negative one made directly in the test.
      - `with_balance()` matches `balance_micro()`.
    - `__str__`: "alice (personal)" and the shared account's name.
  - Check: `makemigrations --check --dry-run` reports no changes.
  - Commit: `feat: add billing accounts and ledger models`

- [x] **2. Per-tier prices**
  - Also tested: a negative price is refused in the admin.
  - Files:
    - `billing/models.py`: `TierPrice`, with `micro_per_token` and `__str__`, and `price_per_1k_tokens` checked to be ≥ 0.
    - `billing/migrations/0002_tierprice.py` (from `makemigrations`).
    - `billing/migrations/0003_seed_tier_prices.py`: hand-written, `get_or_create`, does nothing on undo.
    - `billing/admin.py`: `TierPriceAdmin` with the price editable in the list. No add or delete (three rows only).
    - `billing/tests/test_prices.py`.
  - Tests:
    - After migrations: Value 1, Standard 3, Premium 10.
    - `micro_per_token`: Value 1,000, Standard 3,000, Premium 10,000. A price of 1.5 gives 1,500. A price of 0.001 gives 1.
    - Seeding again does not overwrite a price an admin changed.
    - The admin list loads. Changing a price in the list saves it. There is no add button and no delete.
  - Commit: `feat: add per-tier token prices`

- [ ] **3. Personal account and 1,000-credit grant for every user**
  - Files:
    - `billing/signals.py`: `post_save` on `User` with `created=True`. In one transaction it creates the personal account and a `signup_grant` of `BILLING_SIGNUP_GRANT_CREDITS`.
    - `billing/apps.py`: connect the signal in `ready()`.
    - `config/settings.py`: `BILLING_SIGNUP_GRANT_CREDITS = 1000`.
    - `billing/migrations/0004_backfill_personal_accounts.py`: hand-written data migration for existing users. It skips users who already have a personal account, and does nothing on undo.
    - `billing/tests/test_signup_grant.py`.
  - Tests:
    - `User.objects.create_user(...)` gives exactly one personal account, with a balance of 1,000 credits and one `signup_grant` entry that has no `created_by`.
    - The sign-up page (`POST /accounts/signup/`) does the same.
    - `create_superuser` does the same.
    - Saving an existing user again does not add a second account or grant.
    - With `override_settings(BILLING_SIGNUP_GRANT_CREDITS=5)`, a new user gets 5 credits.
    - Deleting a user whose personal account has ledger entries raises `ProtectedError`. The user, the account, and the entries all still exist afterwards.
    - The backfill function:
      - gives a user without an account one account and 1,000 credits
      - leaves a user who already has one unchanged
      - running it twice changes nothing
    - The existing accounts, auth, and catalog tests still pass.
  - Check: `venv/bin/python manage.py migrate` backfills your dev database. alice and your admin user each get a personal account with 1,000 credits.
  - Commit: `feat: give every user a personal account with sign-up credits`

- [ ] **4. Billing admin: shared accounts, members, credit grants**
  - Files:
    - `billing/admin.py`:
      - `BillingAccountAdmin`: list with balance; filter; search; add = shared only; members picker only for shared; kind and owner read-only on personal accounts; read-only ledger inline; **Grant credits** link; no delete.
      - `LedgerEntryAdmin`: the add form is the grant form (account, amount in credits, note). It sets `kind=admin_grant` and `created_by`. Entries cannot be changed or deleted. The list shows account, kind, amount in credits, note, created by, and time, with filters by kind and account.
    - `billing/forms.py`: `GrantForm`, which takes the amount in credits and turns it into µc through `credits_to_micro`.
    - `billing/tests/test_admin.py`.
  - Tests (as a superuser):
    - The account list loads and shows balances.
    - Adding a shared account with a name and two members works, and its kind is `shared`.
    - Adding one with no name fails.
    - A personal account's page has no members picker, and its kind and owner cannot be changed.
    - The account delete page returns 403, and there is no delete action.
    - Granting 250.5 credits:
      - creates one `admin_grant` entry of 250,500,000 µc, with `created_by` set to the admin
      - the balance goes up by 250.5
    - Granting 0, a negative amount, or 7 decimals is refused with a form error, and no entry is made.
    - Opening an existing ledger entry shows it read-only. Change and delete are refused.
    - A logged-in non-staff user cannot open the admin grant page (redirected to the admin login).
  - Commit: `feat: add billing admin with shared accounts and credit grants`

- [ ] **5. Show billing accounts on the home page**
  - Files: `config/views.py` (pass `BillingAccount.objects.for_user(user).with_balance()`), `templates/home.html`, `config/tests.py`.
  - Tests:
    - A new user sees "Your billing accounts" and their personal account with 1,000 credits.
    - A member of a shared account also sees that account and its balance.
    - Shared accounts they are not a member of, and other people's personal accounts, are not shown.
  - Commit: `feat: show billing accounts and balances on the home page`

- [ ] **6. Record footguns**
  - Files: `doc/wiki/footguns/every-user-gets-a-billing-account.md` (new).
  - Content:
    - The `post_save` signal runs for every new `User`: in tests, in `createsuperuser`, and in the admin.
    - So tests that make users also make accounts and 1,000-credit grants. Tests must not assume the billing tables are empty.
    - Data migrations do not fire signals, so the backfill migration creates accounts itself.
  - Commit: `docs: record billing account footguns`

## Done when

- `venv/bin/python manage.py check` and `venv/bin/python manage.py test` pass.
- `venv/bin/python manage.py makemigrations --check --dry-run` reports no changes.
- `venv/bin/python manage.py migrate` has nothing left to apply.
- No floats are used for credits anywhere in `billing/`. A test checks that `credits_to_micro` refuses a float.

## At rendezvous (human does this)

Start the server in your own terminal: `venv/bin/python manage.py runserver`. Then:

1. Log in as `alice`. The home page shows **Your billing accounts: alice (personal): 1,000 credits**.
2. Log out. Sign up a new user, e.g. `bob`. Their home page shows **bob (personal): 1,000 credits**.
3. Log out. Log in at http://127.0.0.1:8000/admin/ as your admin user. Under **Billing**, open **Tier prices**. You see Value 1, Standard 3, Premium 10. Change Value to `1.5` and click **Save**. Then change it back to `1`.
4. Open **Billing accounts** → **Add billing account**. Name it `Study group` and add `alice` and `bob` as members. Save.
5. On the `Study group` page, click **Grant credits**. Enter `500` and the note `First grant`. Save. Back in **Billing accounts**, `Study group` shows a balance of 500.
6. Try to grant `0`. You should see an error.
7. Open **alice (personal)**. There is no members picker and no **Delete** button.
8. Log in as `alice` again. The home page shows both **alice (personal): 1,000 credits** and **Study group: 500 credits**.
9. Log in as `bob`. They see their own personal account and **Study group**, and not alice's personal account.
