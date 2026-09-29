"""Credit amounts are stored as integers in micro-credits (µc).

1 credit = 1,000,000 µc. With prices of up to 3 decimals per 1K tokens,
every per-token price is a whole number of µc, so charges are exact.
Never use float for credits: only int (µc) and Decimal (credits).
"""
from decimal import Decimal

MICRO_PER_CREDIT = 1_000_000


def credits_to_micro(amount):
    """Credits (Decimal or int) -> µc (int). Raises ValueError past 6 decimals."""
    if isinstance(amount, bool) or not isinstance(amount, (Decimal, int)):
        raise TypeError('credits must be a Decimal or int, not ' + type(amount).__name__)
    micro = Decimal(amount).scaleb(6)
    if micro != micro.to_integral_value():
        raise ValueError('credits can have at most 6 decimal places')
    return int(micro)


def micro_to_credits(micro):
    """µc (int) -> credits (Decimal), exact."""
    return Decimal(micro).scaleb(-6)


def format_credits(micro):
    """µc -> '1,000', '999.817', '0.000183', '-1.5'."""
    text = f'{micro_to_credits(micro):,.6f}'.rstrip('0').rstrip('.')
    return '0' if text in ('', '-0') else text
