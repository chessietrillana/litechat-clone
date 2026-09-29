# TODO

Build order from `doc/study/1790660517_litechat-core.md`. Each item is one plan.

## Done

- [x] 1. Project setup (Django 5.2, `.env` loading, admin, smoke tests). Plan: `doc/plan/1790661129_project-setup.md`.
- [x] 2. Auth: sign up, log in, log out (username + password, no email), base template, login-required home page. Plan: `doc/plan/1790661940_auth.md`.
- [x] 3. Model catalog: `LLMModel` with provider and tier, admin on/off (no delete), three seeded models, Models page. Plan: `doc/plan/1790663929_model-catalog.md`.
- [x] 4. Proxy client: `send_chat()`, one adapter per interface, 30 s timeout, no auto-retry, `proxy_smoke` live check. Plan: `doc/plan/1790662553_proxy-client.md`.
- [x] 5. Billing accounts: personal (auto, 1,000 sign-up credits) and shared accounts, ledger, balance, admin grants, per-tier prices, credits stored as micro-credits. Plan: `doc/plan/1790664853_billing-accounts.md`.
- [x] 6. Chat sessions: Litechat-style layout (sidebar + chat, bubbles, input at the bottom), new chat with model and account fixed at start (Q20), full history each turn (Q22), title from the first message (Q23), sidebar list newest activity first, Send-button script, proxy log lines on the console. Plan: `doc/plan/1790666245_chat-sessions.md`.

## Next

- [ ] 7. Metering: charge per turn at the tier price (Q5–Q9), store the price on each charge (Q10), charge only when the proxy returns usage (Q16), block sending at balance <= 0 (Q14–15), usage page listing the user's charges (Q28).
  - Token counts are already saved on each reply (`ChatMessage`). Add the charge inside the same transaction in `chat/services.py`.
  - Decide: charge for an empty reply that reported usage? It is not saved today.
- [ ] 8. Sidebar: rename and delete sessions (delete hides; charges stay, Q21). The list and reopening are done in plan 6.

## Waiting on the human

Nothing. Every open question in the study has an answer (section 14).

## Later (not planned yet)

- [ ] Password change and password reset (reset needs email).
- [ ] A way to take credits away (negative admin adjustment). Grants must be > 0 for now.
- [ ] Block sending from two tabs at once (see `doc/wiki/footguns/chat-waits-for-the-reply.md`).
- [ ] Streaming or a "typing" sign while waiting (streaming is out of scope for now).

## Also

- [x] Human: confirm the project-setup browser check (admin login works). Confirmed 2026-09-29: saw Groups and Users.
- [x] Human: confirm the auth browser check. Confirmed 2026-09-29: sign-up, weak-password error, log out, failed and successful login, alice in the admin.
- [x] Human: confirm the model-catalog browser check. Confirmed 2026-09-29: /models/ shows all 3 in tier order, turning one off hides it, turning it on shows it.
- [x] Human: confirm the billing-accounts browser check. Confirmed 2026-09-29: steps 1–7, 9, 10 passed (step 8, the user-delete check, skipped; a test covers it).
- [x] Human: confirm the chat-sessions browser check. Confirmed 2026-09-29: steps 1–12 passed, including the Send-button script and the no-JavaScript check.
- [ ] Human: run `venv/bin/python manage.py proxy_smoke` in your own terminal and confirm all three interfaces answer.
