from decimal import Decimal

from django import template

from billing.units import format_credits

register = template.Library()


@register.filter
def credits(micro):
    """{{ amount_micro|credits }} -> '1,000'."""
    return format_credits(micro)


@register.filter
def thousands(number):
    """{{ 1950|thousands }} -> '1,950'. None -> '0'."""
    return f'{number or 0:,}'


@register.filter
def negate(number):
    """{{ -585000|negate }} -> 585000. Charges are stored negative, shown as a cost."""
    return -number


@register.filter
def price(value):
    """{{ Decimal('10.000')|price }} -> '10'; '0.500' -> '0.5'."""
    return f'{Decimal(value).normalize():f}'
