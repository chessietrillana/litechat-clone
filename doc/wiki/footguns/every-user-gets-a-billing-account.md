# Every new user gets a billing account (and users can't be deleted)

## What happens

`billing/signals.py` listens for `post_save` on `User`. When a user is created, it also makes:

- a personal billing account, and
- a `signup_grant` ledger entry of 1,000 credits (`BILLING_SIGNUP_GRANT_CREDITS`).

This runs for **every** way a user is made:

- the sign-up page
- `createsuperuser` (so admins get 1,000 credits too)
- "Add user" in the Django admin
- **every `User.objects.create_user(...)` in tests**

It does not run for:

- `bulk_create`, which skips signals
- fixtures loaded with `loaddata` (`raw=True`)
- data migrations, which never fire signals. That is why `0004_backfill_personal_accounts.py` creates accounts itself.

## Rules for tests

- Do not assume the billing tables are empty. A test that makes users also has their accounts and grants.
- To get a user's personal account, look it up (`BillingAccount.objects.get(owner=user)`). Don't create one: a second personal account breaks a database rule.
- To test "a user from before billing existed", make the user with `bulk_create`.

## Users can't be deleted

- `BillingAccount.owner` cascades, but `LedgerEntry.account` is `PROTECT`.
- So deleting a user tries to delete their personal account, and the account's ledger entries block it with `ProtectedError`.
- Every user has a sign-up grant entry, so **in practice no user can be deleted**, in the admin or in code.
- The admin's delete page for a user shows that the deletion is blocked by protected ledger entries.

To lock someone out, untick **Active** on the user in the admin.

This is on purpose: the ledger must keep its full history (human's decision in the billing-accounts plan review).
