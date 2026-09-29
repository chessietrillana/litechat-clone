# Deleted chats are only hidden

## What happens

When a user clicks **Delete** on a chat, nothing is removed from the database (study NOTE Q21).

- `ChatSession.hidden_at` is set to the time of the delete. That is all.
- The chat, its messages, and its charges all stay.
- Admins still see the chat in **Chat → Chat sessions**. The **Deleted by user** filter shows only these chats.
- For the user, the chat is gone: it leaves the sidebar, and its chat, rename, and delete pages are Not found (404).
- The **Usage** page still lists its charges, shown as "<title> (deleted)" with no link.

There is no undelete yet.

## Every user-facing lookup must use `visible()`

The model's queryset has `visible()`, which leaves out hidden chats. Plain `.all()` does not.

- A new page that lists chats with `request.user.chat_sessions.all()` would show deleted chats again.
- A new page that finds one chat must use `own_session(request, pk)` in `chat/views.py`. It checks the owner and leaves out hidden chats.
- The admin uses `.all()` on purpose.

## A send can finish after the delete

The chat page waits up to 30 seconds for the proxy (see [the chat page waits for each reply](chat-waits-for-the-reply.md)).

- If the user deletes the chat in another tab during that wait, the send still finishes.
- The turn is saved to the hidden chat and charged. The tokens were really used.
- The page then redirects to the chat, which is Not found.

A send that starts after the delete is refused. The view gives 404, and `send_turn` also refuses a hidden chat before the proxy call.

## Code

- The field and `visible()`: `chat/models.py`.
- The views: `own_session`, `delete_session`, `rename_session` in `chat/views.py`.
- The Usage page: `billing/templates/billing/usage.html`.
