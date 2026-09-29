# Plan: chat sessions

Based on: `doc/study/1790660517_litechat-core.md` (build order item 6; section 9; NOTEs on Q20, Q22, Q23, Q24, Q25, Q26).

Goal:

- A user starts a chat by picking a model and a billing account, then typing the first message.
- Each turn sends the full history to the proxy and saves both messages.
- The app gets a chat layout like Litechat: a left sidebar and the chat on the right.
  - Messages show as bubbles. The input box sits at the bottom.
  - The sidebar lists the user's sessions, newest first, with a **New chat** button.

**Not in this plan:**

- Plan 7 (metering): charging per turn, the price on each charge (Q10), blocking at balance ≤ 0 (Q14–15), no charge on failure (Q16), and the usage page (Q28).
- Plan 8 (sidebar): rename, delete (hide, Q21).

This plan saves the token counts of every reply, so plan 7 can charge from them.

Branch: `feat/chat-sessions`. The plan file is committed on this branch, as asked, and not on `main`.

## What exists now

- Packages: Django 5.2.17, python-dotenv 1.2.3 (plus asgiref, sqlparse). Nothing new is needed.
- Apps: `accounts`, `proxy`, `catalog`, `billing`. No `chat` app yet.
- `proxy.client.send_chat(interface, model, history)` works and is tested. The history must start and end with a user message, and no message may be empty.
- `LLMModel.objects.active()` gives the models users can pick. `provider` is the proxy interface name.
- `BillingAccount.objects.for_user(user).with_balance()` gives the accounts a user may bill to, with balances.
- The home page (`/`) says hello and lists billing accounts. The header has **Models**, the username, and **Log out**.
- CSS: one plain file, `static/css/site.css`. The main column is 40rem wide.

## Decisions made in this plan

- **New app `chat`.**
- **`ChatSession`:**

  | Field | Notes |
  |---|---|
  | `user` | The owner. Only they can see it. |
  | `llm_model` | The `LLMModel`. Fixed at start (NOTE Q20). Protected: a model with sessions can't be deleted (the admin already has no delete). |
  | `billing_account` | The `BillingAccount`. Fixed at start (NOTE Q20). Protected. |
  | `title` | From the first message (NOTE Q23). |
  | `created_at` | |
  | `updated_at` | Set on every new turn. The sidebar sorts by this. |

  - There is no field or page to change the model or account after the start.
  - Plan 8 adds a "hidden" field for delete (Q21). Not added now.
- **`ChatMessage`** (not `Message`, which is already the proxy's type):

  | Field | Notes |
  |---|---|
  | `session` | |
  | `role` | `user` or `assistant` |
  | `content` | The text |
  | `input_tokens`, `output_tokens`, `cached_tokens` | Assistant replies only. Empty if the proxy did not report them. Plan 7 charges from these (Q8, Q16). |
  | `finish_reason` | Assistant replies only. The normalized reason (`stop`, `length`, ...). |
  | `response_id` | Assistant replies only. The proxy's ID, for support. |
  | `created_at` | |

  Ordered by `created_at`, then `id`.
- **Title (NOTE Q23):** the first 6 words of the first message, cut to at most 60 characters, with "…" if cut. Line breaks become spaces. If the message has no words left, the title is "New chat".
- **"Newest first" means most recent activity.** Sessions sort by `updated_at`, so a chat you just replied in moves to the top. This is how Litechat and most chat apps work. If you'd rather sort by start time, it is a one-word change.
- **A turn is saved only when the proxy answers.**
  - We build the history from the saved messages plus the new user message, call `send_chat`, and only then save the user message and the reply together, in one transaction.
  - If the proxy fails (timeout, error, empty reply), nothing is saved. The page shows the error's `user_message`, and the text stays in the input box, so the user can press **Send** again.
  - Why: the history always goes user, assistant, user, assistant. A failed turn never leaves a user message without a reply. And plan 7 can add the charge to the same transaction.
  - The proxy call is made **outside** the transaction, so the database is not locked for up to 30 seconds.
- **Starting a chat is one form**, like Litechat: model, billing account, and the first message.
  - The session is created only when the first reply arrives. So a failed first message leaves no empty session in the sidebar.
- **Checks on every send:**
  - The session belongs to the user. Otherwise 404.
  - The model is still active. If an admin turned it off, sending is refused with "This model has been turned off. Start a new chat with another model." The old messages still show.
  - The billing account is still in `for_user(user)`. If an admin removed them from a shared account, sending is refused with "You can no longer use this billing account. Start a new chat."
  - The message is not blank, and is at most 20,000 characters.
- **Balance is not checked yet.** Plan 7 blocks at ≤ 0. In this plan, chatting is free.
- **Reply options:** max 1,024 tokens (NOTE Q24), thinking off (NOTE Q25), no system prompt (NOTE Q26). `send_chat` already does all three by default.
- **No history cap (NOTE Q22).** Every turn sends every message.
- **Cut-off replies:** if `finish_reason` is `length`, the bubble shows a small note: "This reply was cut off at the length limit."
- **Text is shown as plain text**, with line breaks kept (`white-space: pre-wrap`). No Markdown. Django escapes it, so HTML in a message is shown, not run.
- **URLs:**

  | URL | Name | What |
  |---|---|---|
  | `/` | `home` | The chat layout with the **new chat** form. Replaces the current home page. |
  | `/chat/new/` | `chat_new` | POST only. Starts a session and sends the first message. |
  | `/chat/<id>/` | `chat_session` | GET: the session. POST: send the next message. |

  - A successful POST redirects to `/chat/<id>/` (post/redirect/get), so reloading does not send twice.
  - A failed POST shows the page again with the error and the text kept, and no redirect.
- **Home page changes:** "Your billing accounts" moves into the account picker, which shows each balance, e.g. "alice (personal) · 1,000 credits". "Hello, alice." stays as the heading of the empty chat area.
- **Layout:**
  - `templates/base.html` keeps the header. It gets a `{% block main %}` so chat pages can use the full width.
  - Other pages (login, sign up, Models) keep the narrow centered column.
  - `templates/chat/layout.html` has the sidebar on the left (16rem) and the chat on the right. The messages scroll. The input box stays at the bottom.
  - Bubbles: user messages on the right, blue. Replies on the left, white with a border.
  - Under 700px wide, the sidebar sits above the chat.
  - Plain CSS in `static/css/site.css`. No framework.
- **A small plain-JS file, `static/js/chat.js`** (human's review). No framework. It runs on the new chat form and the session send form:
  - Once a message is submitted, the **Send** button is disabled and shows "Waiting for reply…". So a double click can't send twice.
  - Enter sends. Shift+Enter adds a new line.
  - Enter does nothing while the box is blank or a send is in progress.
  - Enter while typing with an input method (e.g. Japanese, `isComposing`) does not send.
  - The script is loaded with `defer` and only on chat pages.
- **Without JavaScript the pages still work:** the forms are normal POST forms. Only these limits come back:
  - The page waits for the reply, up to 30 seconds, with no sign of progress.
  - Enter does not send. The user clicks **Send**.
  - Clicking **Send** twice fast can send two turns.
  - These go in the footgun doc.
- **Even with JavaScript:** the browser still waits up to 30 seconds for the reply. The button text is the only sign of progress. Sending from two tabs at once is not blocked.
- **Admin:** a view-only **Chat sessions** page with the messages inline. No add, change, or delete. It helps check that turns and token counts are saved.
- **Logging:** add a `LOGGING` setting so the `proxy` INFO lines show in the runserver terminal (TODO "Later"). The lines hold no message text and no keys.

## Steps

- [x] **1. Chat app: session and message models**
  - Also: `updated_at` is set by the chat services, not `auto_now`, so a later rename (plan 8) won't move a chat to the top. `ChatMessage.was_cut_off` is true when `finish_reason` is `length`. Test helpers live in `chat/tests/helpers.py`.
  - Files:
    - `chat/` (new app, `venv/bin/python manage.py startapp chat`). Add `"chat"` to `INSTALLED_APPS`.
    - `chat/models.py`: `ChatSession`, `ChatMessage`, and `make_title(text)`.
    - `chat/migrations/0001_initial.py` (from `makemigrations`).
    - `chat/admin.py`: view-only `ChatSessionAdmin` with a messages inline.
    - `chat/tests/` package with `test_models.py`. Remove the generated `chat/tests.py` stub, as for `proxy` and `billing`. The human confirmed this deletion.
  - Tests:
    - `make_title`:
      - "What is the capital of France?" → "What is the capital of France?"
      - A long message → its first 6 words plus "…"
      - A single 100-letter word → the first 60 characters plus "…"
      - Line breaks become spaces
      - Only spaces → "New chat"
    - Messages come back in the order they were made.
    - `session.history()` gives `proxy.types.Message` objects with the right roles and text.
    - Deleting a model or billing account that has a session raises `ProtectedError`.
    - The admin list and a session page load for a superuser. There is no add or delete.
  - Commit: `feat: add chat session and message models`

- [x] **2. Chat services: start a chat and send a turn**
  - Also tested: a reply with no usage saves empty token counts; exactly 20,000 characters is allowed.
  - Files:
    - `chat/services.py`:
      - `start_session(user, llm_model, billing_account, text)` returns a new session.
      - `send_turn(session, text)` returns the reply `ChatMessage`.
      - Both build the history, call `send_chat`, and save in one transaction only on success.
      - `ChatError(user_message)` for refused sends: model turned off, account not allowed, blank or too long text, empty reply.
      - `ProxyError` is passed on unchanged. The view shows its `user_message`.
    - `chat/tests/test_services.py`. `send_chat` is mocked. No network.
  - Tests:
    - `start_session` saves the session with the title, the user message, and the reply with its token counts, finish reason, and response ID.
    - `send_turn` sends the **full** history: after 3 turns, the 4th call gets 7 messages, in order, and the right interface and `proxy_model_id`.
    - `send_turn` updates `updated_at`.
    - A `ProxyTimeout` saves nothing: no new messages, no new session, `updated_at` unchanged.
    - An empty reply saves nothing and raises `ChatError`.
    - A turned-off model is refused before `send_chat` is called.
    - A billing account the user can't use is refused before `send_chat` is called. This covers starting with someone else's account, and being removed from a shared account.
    - Blank text and text over 20,000 characters are refused.
  - Commit: `feat: add chat services that send the full history to the proxy`

- [x] **3. Chat layout, sidebar, and the new chat page**
  - Also:
    - The chat templates live in the app, `chat/templates/chat/`, like `catalog`'s.
    - The messages list moved into `templates/_messages.html`, so both layouts show it.
    - A bare `/chat/<id>/` page (title and messages as text) was added here, so the new chat redirect has somewhere to go. Step 4 gives it bubbles and the send box.
    - `POST /` returns 405.
  - Files:
    - `templates/base.html`: add `{% block main %}` around the current main column.
    - `templates/chat/layout.html` (new): sidebar with **New chat** and the session list (current one highlighted), and the chat area.
    - `templates/chat/new.html` (new): "Hello, <username>.", and the form: model (name, provider, tier), billing account (with balance), and message.
    - `templates/home.html`: removed. Its content moves into `chat/new.html`. The human confirmed this deletion.
    - `chat/forms.py`: `NewChatForm` (model and account choices limited to active models and `for_user`).
    - `chat/views.py`: `home` (GET the form) and `new_chat` (POST). `config/views.py` is removed and `/` points to `chat.views.home`. The human confirmed this deletion.
    - `chat/urls.py`, `config/urls.py`.
    - `static/css/site.css`: layout, sidebar, form at the bottom.
    - `config/tests.py`: move the home tests to `chat/tests/test_views.py` and keep what they check.
  - Tests:
    - `/` still redirects visitors to the login page.
    - `/` shows "Hello, alice.", the **New chat** button, and the form.
    - The model picker lists only active models.
    - The account picker lists the user's personal account with "1,000 credits" and shared accounts they belong to, and not others (the old home page tests, moved).
    - The sidebar lists only the user's own sessions, newest activity first.
    - `POST /chat/new/` with a mocked reply redirects to the new session.
    - `POST /chat/new/` with another user's account or a turned-off model shows a form error and makes nothing.
    - `POST /chat/new/` when the proxy fails shows the error, keeps the text, and makes no session.
    - `GET /chat/new/` returns 405.
  - Commit: `feat: add chat layout with session sidebar and new chat page`

- [x] **4. Session page: bubbles and the send box**
  - Also:
    - The message list starts scrolled to the newest message, using CSS only (`flex-direction: column-reverse`).
    - Each bubble has a hidden "You:" or model-name label for screen readers.
    - Tested: line breaks are kept, a missing session is 404, and posting a different model with the form changes nothing.
  - Files:
    - `templates/chat/session.html` (new): title, model and account shown at the top, the message bubbles, and the send form at the bottom.
    - `chat/views.py`: `session_detail` (GET shows, POST sends).
    - `chat/urls.py`, `static/css/site.css` (bubbles).
    - `chat/tests/test_views.py`.
  - Tests:
    - The owner sees all messages in order, with user and reply bubbles marked by class.
    - Another user gets 404 for GET and POST. A visitor is sent to log in.
    - POST with a mocked reply saves the turn and redirects to the same page.
    - POST when the proxy fails shows the error's `user_message`, keeps the text, and saves nothing.
    - POST to a session whose model is turned off shows the "turned off" message. The old messages still show.
    - A reply with `finish_reason` `length` shows the cut-off note.
    - `<script>` in a message is shown as text, not run.
    - The model and account shown can't be changed: the page has no picker for them.
  - Commit: `feat: add chat session page with message bubbles`

- [ ] **5. Send button script: no double send, Enter to send**
  - Files:
    - `static/js/chat.js` (new): plain JS, as described in the decisions.
    - `templates/chat/layout.html`: load it with `<script defer>`.
    - `templates/chat/new.html`, `templates/chat/session.html`: mark the send forms with `data-chat-form`, and give the button its waiting text in `data-waiting-text`.
    - `chat/tests/test_views.py`.
  - Tests:
    - Django tests can't run JavaScript. They check the wiring:
      - Both chat pages load `js/chat.js`, and the login page does not.
      - Both send forms have `data-chat-form`, a normal `method="post"` and `action`, and a real submit button. So the page works without JS.
      - The static file is found (`finders.find('js/chat.js')`).
    - The JS itself is checked by the human at rendezvous (steps below).
  - Commit: `feat: disable Send while waiting and send on Enter`

- [ ] **6. Show proxy log lines in the terminal**
  - Files: `config/settings.py` (`LOGGING`: the `proxy` logger at INFO to the console), `doc/wiki/footguns/proxy-logs-not-shown.md` (say it's fixed).
  - Tests: a test with `assertLogs('proxy', 'INFO')` still passes. A test checks that the `proxy` logger's level is INFO.
  - Commit: `feat: show proxy log lines in the console`

- [ ] **7. Record footguns**
  - Files: `doc/wiki/footguns/chat-waits-for-the-reply.md` (new):
    - The browser waits up to 30 seconds for each reply. With JS, the button says "Waiting for reply…". That is the only sign of progress.
    - Without JS: no progress sign, Enter does not send, and a double click on **Send** can send two turns.
    - Sending from two tabs at once is not blocked, even with JS.
    - After the browser's **Back** button, the Send button could still be disabled. The script re-enables it when the page is shown again (`pageshow`).
    - A failed turn saves nothing, on purpose. The text stays in the box.
    - Sessions sort by last activity, not by start time.
  - Commit: `docs: record chat session footguns`

## Done when

- `venv/bin/python manage.py check` and `venv/bin/python manage.py test` pass.
- `venv/bin/python manage.py makemigrations --check --dry-run` reports no changes.
- `venv/bin/python manage.py migrate` has nothing left to apply.
- No test calls the real proxy.

## At rendezvous (human does this)

This uses the real proxy and your keys. Chatting is free until plan 7.
Start the server in your own terminal: `venv/bin/python manage.py runserver`. Then:

1. Log in as `alice`. You see the chat layout: an empty sidebar with **New chat**, and "Hello, alice." with the new chat form.
2. The model picker lists the 3 models. The account picker shows **alice (personal) · 1,000 credits** and **Study group · 500 credits**.
3. Pick **Gemini 3.8 Flash** and **alice (personal)**. Type `What is the capital of France? Answer in one sentence.` Click **Send**. After a few seconds you are on the session page. Your message is a bubble on the right, and the reply is on the left. The sidebar shows the title "What is the capital of France?…".
4. Type `And of Italy?` and press **Enter**. The Send button turns grey and says "Waiting for reply…" until the page reloads. The reply should talk about Rome. This shows the full history was sent.
   - Before sending, press **Shift+Enter** in the box. It adds a new line and does not send.
   - Double-click **Send** on the next message. Only one turn is added.
5. Click **New chat**. Start a second chat with **GPT-5.6 Luna** and **Study group**. It appears at the top of the sidebar.
6. Click the first chat in the sidebar. It opens with all its messages. Send one more message. It moves to the top of the sidebar.
7. Watch the runserver terminal. Each turn prints a `proxy call ok` line with token counts, and no message text.
8. In the admin, turn off **Gemini 3.8 Flash**. Open the first chat and try to send. You see "This model has been turned off...". Turn the model back on.
9. Log in as `bob`. Their sidebar is empty. Open alice's chat URL (e.g. `/chat/1/`). You get "Not found".
10. In the admin, open **Chat sessions**. You see alice's two chats, with messages and token counts.
11. Make the window narrow. The sidebar moves above the chat.
12. Optional: turn off JavaScript in the browser and send a message. It still works: you click **Send** and the page waits for the reply.
