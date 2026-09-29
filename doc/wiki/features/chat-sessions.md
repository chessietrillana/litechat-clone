# Chat sessions

Users chat with a model in sessions. A session has one model and one billing account, picked at the start.
Every turn sends the full history to the proxy. The app looks like Litechat: a sidebar on the left, the chat on the right.

Chatting is **free for now**. Charging per turn, blocking at balance ≤ 0, and the usage page come in the metering plan (plan 7).
Rename and delete come in the sidebar plan (plan 8).

Plan: `doc/plan/1790666245_chat-sessions.md`. Decisions: study NOTEs Q20, Q22–Q26.

## How it works for users

1. The home page (`/`) is the **new chat** page: "Hello, <username>.", and a form at the bottom:
   - **Model**: active models only, e.g. "Gemini 3.8 Flash (Google, Value)".
   - **Billing account**: accounts the user may bill to, with balances, e.g. "alice (personal) · 1,000 credits".
   - **Message**: the first message.
2. **Send** starts the chat. When the reply arrives, the user is taken to the session page (`/chat/<id>/`).
3. The session page shows the title, the model and account, the messages as bubbles, and the send box at the bottom.
   - Your messages are on the right (blue). Replies are on the left (white).
   - The list opens scrolled to the newest message.
   - A reply that hit the length limit shows "This reply was cut off at the length limit."
4. The sidebar lists the user's chats, most recent activity first, and a **New chat** button. The open chat is highlighted.

Under 700px wide, the sidebar sits above the chat.

## Rules

- **Model and account are fixed at the start** (NOTE Q20). The session page has no picker for them.
- **Full history, no cap** (NOTE Q22). Turn 4 sends 7 messages.
- **Title** (NOTE Q23): the first 6 words of the first message, at most 60 characters, with "…" if cut. See `make_title` in `chat/models.py`.
- **Reply options:** max 1,024 tokens (Q24), thinking off (Q25), no system prompt (Q26). These are `send_chat`'s defaults.
- **Only the owner** can see or send in a session. Others get 404.
- **Checks on every send**, before the proxy is called:
  - The message is not blank and is at most 20,000 characters.
  - The model is still active. If not: "This model has been turned off. Start a new chat with another model."
  - The account is still one the user may bill to (`BillingAccount.objects.for_user`). If not: "You can no longer use this billing account. Start a new chat."
- **A turn is saved only when the proxy answers.**
  - The proxy is called first, outside any database transaction. Then the user message and the reply are saved together, in one transaction.
  - On a failure (timeout, proxy error, empty reply), nothing is saved. The error shows above the box, and the text stays in the box.
  - A failed first message makes no session.
  - Plan 7 will add the charge to the same transaction.
- **Text is plain text.** Line breaks are kept. No Markdown. HTML in a message is shown as text, not run.
- A successful send redirects back to the page (post/redirect/get), so reloading does not send again.

## Send button script

`static/js/chat.js`, plain JS, loaded only on chat pages:

- After a send, **Send** is disabled and says "Waiting for reply…". A double click sends once.
- Enter sends. Shift+Enter adds a new line. Enter does nothing while the box is blank, a send is in progress, or an input method is composing.
- After **Back**, the button is turned on again.

Without JavaScript the forms still work. See [the footgun](../footguns/chat-waits-for-the-reply.md).

## Data

| Model | Fields |
|---|---|
| `ChatSession` | `user`, `llm_model` (protected), `billing_account` (protected), `title`, `created_at`, `updated_at` (set on every turn; the sidebar sorts by it) |
| `ChatMessage` | `session`, `role` (`user` or `assistant`), `content`, and for replies: `input_tokens`, `output_tokens`, `cached_tokens`, `finish_reason`, `response_id`, `created_at` |

- Token counts are empty if the proxy did not report them. Plan 7 charges from them.
- A model or billing account that has sessions can't be deleted (`ProtectedError`).

## Code

| File | What |
|---|---|
| `chat/models.py` | `ChatSession`, `ChatMessage`, `make_title` |
| `chat/services.py` | `start_session`, `send_turn`, `ChatError`. The only chat code that calls `send_chat`. |
| `chat/forms.py` | `NewChatForm` (choices limited to the user), `MessageForm` |
| `chat/views.py` | `home`, `new_chat`, `session_detail` |
| `chat/templates/chat/` | `layout.html` (sidebar), `new.html`, `session.html` |
| `static/css/site.css` | Layout, sidebar, bubbles |
| `static/js/chat.js` | Send button script |

## Admin

**Chat → Chat sessions**: view only. The list shows title, user, model, account, and times. Each session shows its messages with token counts. No add, change, or delete.

## Logs

Each proxy call prints one line in the runserver terminal, with tokens and time and no message text, e.g. `INFO proxy: proxy call ok interface=google ... input_tokens=183 output_tokens=9 ...`. See `LOGGING` in [Configuration](configuration.md).

## Tests

All in `chat/tests/`. `send_chat` is always mocked. No test calls the proxy.

- `test_models.py`: titles, message order, `history()`, protected model and account, the view-only admin.
- `test_services.py`: what is saved, full history in order, `updated_at`, nothing saved on failure or empty reply, turned-off model, account rules, text limits.
- `test_views.py`:
  - home page: greeting, pickers, balances, only the user's accounts (moved from `config/tests.py`)
  - sidebar: own chats only, order, current chat marked
  - new chat: redirect, form errors, proxy failure keeps the text
  - session page: bubbles, 404 for others, send, errors, cut-off note, HTML escaped, line breaks, model can't be changed
  - script wiring: both forms are normal POST forms with `data-chat-form`, the script loads only on chat pages
