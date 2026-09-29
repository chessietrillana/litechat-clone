from django import template

from billing.units import format_credits

register = template.Library()


@register.filter
def credits(micro):
    """{{ amount_micro|credits }} -> '1,000'."""
    return format_credits(micro)
