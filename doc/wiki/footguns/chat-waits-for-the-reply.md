# The chat page waits for each reply

## What happens

There is no streaming. When you click **Send**, the browser posts the form and waits for the whole reply. The proxy call can take up to 30 seconds (`PROXY_TIMEOUT_SECONDS`).

## With JavaScript (normal case)

`static/js/chat.js` runs on the chat pages:

- After you send, the **Send** button turns grey and says "Waiting for reply…". That is the only sign of progress. There is no "typing" animation.
- The button stays disabled, so a double click sends only once.
- Enter sends. Shift+Enter adds a new line.
- Enter does nothing while the box is blank, or while a send is already in progress.
- Enter while typing with an input method (e.g. Japanese) picks a word and does not send.

Still not blocked, even with JavaScript:

- **Sending from two tabs at once.** Both turns are sent. Each tab sends the history it had, so the two replies may not see each other's messages.

## Without JavaScript

The forms are normal POST forms, so chat still works. But:

- There is no progress sign at all. The page just loads for a while.
- Enter adds a new line. You must click **Send**.
- A double click on **Send** can send two turns.

## The Back button

Browsers can restore a page from their cache when you press **Back**. The Send button could then still be disabled and say "Waiting for reply…".
The script turns it back on when the page is shown again (the `pageshow` event).

## A failed turn saves nothing, on purpose

If the proxy times out or fails, nothing is saved: not your message and not a reply. The error shows above the box, and your text stays in the box. Press **Send** to try again.

- Why: the history must always go user, reply, user, reply. A saved message with no reply would break the next turn.
- A failed **first** message makes no chat at all. So there are no empty chats in the sidebar.
- An empty reply from the model counts as a failure too.

## Sidebar order

The sidebar sorts chats by **last activity**, not by when they started. Sending a message in an old chat moves it to the top.
