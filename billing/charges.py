"""Charges: ledger entries that take credits away for used tokens."""
from billing.models import LedgerEntry


def record_charge(account, user, tokens, tier_price):
    """Charge `tokens` at `tier_price` to `account`. Return the new entry.

    The price is copied onto the entry, so later price changes don't touch it.
    The balance may go below 0: the cost is only known after the reply.
    """
    return LedgerEntry.objects.create(
        account=account,
        amount_micro=-tier_price.cost_micro(tokens),
        kind=LedgerEntry.Kind.CHARGE,
        note=f'{tier_price.get_tier_display()} tier',
        created_by=user,
        tokens=tokens,
        price_per_1k_tokens=tier_price.price_per_1k_tokens,
    )
