# Sidebar: rename and delete chats

The sidebar lists the user's chats (from plan 6). Each chat has a "⋯" menu with **Rename** and **Delete**.
Delete only hides the chat. Its messages and charges stay.

Plan: `doc/plan/1790668837_sidebar.md`. Decisions: study NOTE Q21, and the human's review of the plan.

## How it works for users

- Click "⋯" next to a chat. It opens a small menu with **Rename** and **Delete**. It is an HTML `<details>` element, so it needs no JavaScript. Screen readers hear "Options for <title>".
- **Rename** opens a page (`/chat/<id>/rename/`) with the title in a box, **Save**, and **Cancel**.
  - After **Save**: back to the chat, with "Chat renamed."
  - An error shows on the same page, and the typed text is kept.
- **Delete** opens a confirm page (`/chat/<id>/delete/`). It says the chat leaves your list, can't be opened again, and that its charges stay on the Usage page.
  - The red **Delete** button deletes it. **Cancel** goes back to the chat.
  - After deleting: the new chat page (home), with "Deleted "<title>"." This is the same for any chat, open or not.
- Both pages use the chat layout, so the sidebar stays on the left and the chat is highlighted.

## Rules

- **Only the owner** can rename or delete a chat. Another user's chat is Not found (404), not Forbidden, so its existence is not shown.
- **Rename:**
  - Spaces at the start and end are removed.
  - A blank title is refused: "Enter a title."
  - At most 100 characters (the size of the `title` column). The box has `maxlength="100"`.
  - Any other text is allowed, even a title another chat has. HTML shows as text.
  - A rename saves only `title`. It does not change `updated_at`, so the chat keeps its place in the sidebar.
- **Delete hides** (NOTE Q21):
  - It sets `ChatSession.hidden_at`. Nothing is removed from the database.
  - The chat leaves the sidebar. Its chat, rename, and delete pages are Not found (404).
  - A send to a deleted chat is refused before the proxy is called. Nothing is saved or charged.
  - Its charges stay in the ledger. The balance does not change.
  - Only a POST deletes. The GET page only asks. A second delete (from another tab) is 404.
  - There is no undelete yet.
- **Usage page:** a deleted chat's charges stay listed. The chat shows as "<title> (deleted)", as plain text with no link.

See [the footgun](../footguns/deleted-chats-are-only-hidden.md): every user-facing lookup must use `visible()`, and a send already waiting when the chat is deleted still finishes and is charged.

## URLs

| URL | Name | View | Methods |
|---|---|---|---|
| `/chat/<id>/rename/` | `chat_rename` | `chat.views.rename_session` | GET, HEAD, POST |
| `/chat/<id>/delete/` | `chat_delete` | `chat.views.delete_session` | GET, HEAD, POST |

Both need login. Other methods get 405.

## Data

- `ChatSession.hidden_at`: date and time, empty = visible. Set by `ChatSession.hide()`.
- `ChatSession.objects.visible()` (also on `user.chat_sessions`) leaves out hidden chats.
- `ChatSession.is_hidden`: true when `hidden_at` is set.

## Admin

**Chat → Chat sessions** stays view only.

- The list has a **Hidden at** column and a **Deleted by user** filter (Yes / No).
- A hidden chat's page still opens, with its messages.

## Code

| File | What |
|---|---|
| `chat/models.py` | `hidden_at`, `ChatSessionQuerySet.visible()`, `hide()`, `is_hidden` |
| `chat/views.py` | `own_session` (the user's own visible chat, or 404), `rename_session`, `delete_session`. `render_chat` lists only visible chats. |
| `chat/forms.py` | `RenameForm`. A plain `Form`, so a refused title never touches the chat shown on the page. |
| `chat/services.py` | `send_turn` refuses a hidden chat (`CHAT_DELETED`). |
| `chat/admin.py` | The column and `DeletedByUserFilter` |
| `chat/templates/chat/` | `layout.html` (the "⋯" menu), `rename.html`, `delete.html` |
| `billing/templates/billing/usage.html` | "(deleted)" with no link |
| `static/css/site.css` | `.session-menu`, `.chat-panel`, `.form-actions`, `.button-danger` |

## Tests

- `chat/tests/test_hide.py`: `hide()`, `visible()`, the sidebar, 404 for GET and POST, `send_turn` refused, charges kept, admin column and filter.
- `chat/tests/test_delete.py`: login, the menu, the confirm page, delete and redirect, charges and balance kept, other users, hidden and missing chats, 405, query count.
- `chat/tests/test_rename.py`: login, the menu, the form, save and redirect, spaces, blank, 100 and 101 characters, HTML as text, place in the sidebar kept, other users, hidden and missing chats, 405.
- `billing/tests/test_usage_page.py`: a deleted chat shows "(deleted)" with no link; query count with deleted chats.
