# TODO

Build order from `doc/study/1790660517_litechat-core.md`. Each item is one plan.

## Done

- [x] 1. Project setup (Django 5.2, `.env` loading, admin, smoke tests). Plan: `doc/plan/1790661129_project-setup.md`.
- [x] 2. Auth: sign up, log in, log out (username + password, no email), base template, login-required home page. Plan: `doc/plan/1790661940_auth.md`.

## Next

- [ ] 3. Model catalog: `LLMModel` table with provider and tier, admin, seed data, models page.
- [ ] 4. Proxy client: one adapter per interface, 30 s timeout, no auto-retry, tests with saved sample JSON.
- [ ] 5. Billing accounts: accounts, ledger, balance, admin credit grants.
- [ ] 6. Chat sessions: pick model and account, chat page, send full history, save messages.
- [ ] 7. Metering: charge per turn, usage and cost per session, block when balance is too low.
- [ ] 8. Sidebar: list, rename, reopen, delete sessions.

## Waiting on the human

Open questions in section 13 of the study. Needed before:

- [ ] Plan 3: models and tiers (Q1–Q4).
- [ ] Plans 5–7: pricing (Q5–Q10), credits and balances (Q11–Q16), billing accounts (Q17–Q20), usage page (Q28).
- [ ] Plans 6 and 8: sessions and chat (Q21–Q26).

Plan 4 (proxy client) does not depend on any open question. It can go next if plan 3 is waiting.

## Later (not planned yet)

- [ ] Password change and password reset (reset needs email).

## Also

- [x] Human: confirm the project-setup browser check (admin login works). Confirmed 2026-09-29: saw Groups and Users.
- [x] Human: confirm the auth browser check. Confirmed 2026-09-29: sign-up, weak-password error, log out, failed and successful login, alice in the admin.
