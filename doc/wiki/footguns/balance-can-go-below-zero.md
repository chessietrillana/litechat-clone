# The balance can go below 0

## What happens

Sending is blocked when an account's balance is 0 or less (study NOTE Q14–15).
But the balance can still end up below 0.

- The cost of a turn is only known after the reply arrives. It depends on the tokens the proxy reports.
- The check happens **before** the proxy call. The charge is saved **after** it.
- So a send at 0.1 credits is allowed. If the reply costs 0.2 credits, the balance ends at −0.1.
- The next send is then blocked.

This is on purpose (the human's decision in plan 7). Nothing is taken back and no reply is thrown away.

## Two sends at once

Two sends that start at the same time both pass the check. Examples:

- two browser tabs on the same chat
- two members of a shared account

Both are charged. So the balance can go further below 0 than one turn's cost. There is no lock. See [the chat page waits for each reply](chat-waits-for-the-reply.md).

## What the user sees

- The chat header always says: "A reply's cost is known only after it arrives, so one reply can take the balance below 0."
- At 0 or less, the input box is replaced by a note: "This billing account has no credits left, so sending is blocked."
- The new chat form still lists the account with its balance. Sending shows "This billing account has no credits left…" and keeps the text.
- The **Usage** page shows the negative balance and says the same thing.

## How to fix a negative balance

An admin grants credits in the admin (**Billing accounts** → the account → **Grant credits**). The grant must be larger than the debt to get above 0.

## Code

- The check: `check_can_send` in `chat/services.py`.
- The charge: `record_charge` in `billing/charges.py`, called inside the same transaction that saves the turn.
