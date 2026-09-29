# TODO

Build order from `doc/study/1790660517_litechat-core.md`. Each item is one plan.

## Done

- [x] 1. Project setup (Django 5.2, `.env` loading, admin, smoke tests). Plan: `doc/plan/1790661129_project-setup.md`.
- [x] 2. Auth: sign up, log in, log out (username + password, no email), base template, login-required home page. Plan: `doc/plan/1790661940_auth.md`.
- [x] 3. Model catalog: `LLMModel` with provider and tier, admin on/off (no delete), three seeded models, Models page. Plan: `doc/plan/1790663929_model-catalog.md`.
- [x] 4. Proxy client: `send_chat()`, one adapter per interface, 30 s timeout, no auto-retry, `proxy_smoke` live check. Plan: `doc/plan/1790662553_proxy-client.md`.
- [x] 5. Billing accounts: personal (auto, 1,000 sign-up credits) and shared accounts, ledger, balance, admin grants, per-tier prices, credits stored as micro-credits. Plan: `doc/plan/1790664853_billing-accounts.md`.
- [x] 6. Chat sessions: Litechat-style layout (sidebar + chat, bubbles, input at the bottom), new chat with model and account fixed at start (Q20), full history each turn (Q22), title from the first message (Q23), sidebar list newest activity first, Send-button script, proxy log lines on the console. Plan: `doc/plan/1790666245_chat-sessions.md`.
- [x] 7. Metering: charge per turn at the tier price (Q5–Q9, cached tokens included, Anthropic cache counts added), the price stored on each charge (Q10), no usage = no charge (Q16), empty replies with usage saved and charged, block sending at balance <= 0 (Q14–15, one turn can go below 0), tokens and cost in the chat, Usage page (Q28). Plan: `doc/plan/1790667382_metering.md`.

- [x] 8. Sidebar: a "⋯" menu on each chat with Rename (blank refused, max 100 characters, keeps its place) and Delete (confirm page; hides the chat, Q21; its URL is 404; charges stay; Usage shows "(deleted)" with no link). Owner only. Plan: `doc/plan/1790668837_sidebar.md`.

## Next

All eight plans in the study's build order are done. Pick the next work from "Later", or ask for a new study.

## Waiting on the human

Nothing. Every open question in the study has an answer (section 14).

## Later (not planned yet)

- [ ] Password change and password reset (reset needs email).
- [ ] A way to take credits away (negative admin adjustment). Grants must be > 0 for now.
- [ ] Block sending from two tabs at once (see `doc/wiki/footguns/chat-waits-for-the-reply.md`).
- [ ] Streaming or a "typing" sign while waiting (streaming is out of scope for now).
- [ ] A lock so two sends at once can't both pass the balance check (see `doc/wiki/footguns/balance-can-go-below-zero.md`).
- [ ] Usage page: totals per account or per month, and a filter by account. Not asked for yet.
- [ ] Undelete a chat (for the user, or for an admin). Deleted chats are only hidden, so this is possible. Not asked for yet.
- [ ] Delete many chats at once, or delete a chat for real. Not asked for yet.

## Also

- [x] Human: confirm the project-setup browser check (admin login works). Confirmed 2026-09-29: saw Groups and Users.
- [x] Human: confirm the auth browser check. Confirmed 2026-09-29: sign-up, weak-password error, log out, failed and successful login, alice in the admin.
- [x] Human: confirm the model-catalog browser check. Confirmed 2026-09-29: /models/ shows all 3 in tier order, turning one off hides it, turning it on shows it.
- [x] Human: confirm the billing-accounts browser check. Confirmed 2026-09-29: steps 1–7, 9, 10 passed (step 8, the user-delete check, skipped; a test covers it).
- [x] Human: confirm the chat-sessions browser check. Confirmed 2026-09-29: steps 1–12 passed, including the Send-button script and the no-JavaScript check.
- [x] Human: confirm the metering browser check. Confirmed 2026-09-29: all 9 steps passed (charges, Usage page, price change keeps old prices, blocking at 0, grant unblocks).
- [x] Human: confirm the sidebar browser check. Confirmed 2026-09-29: all 10 steps passed (rename, blank refused, keeps its place, cancel, delete, 404, Usage "(deleted)", admin filter, other user gets 404).
- [x] Human: run `venv/bin/python manage.py proxy_smoke` in your own terminal and confirm all three interfaces answer.
