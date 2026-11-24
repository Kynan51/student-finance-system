from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def ksh(value, decimals=2):
    """Format a number as Kenyan shillings: 1234.5 -> 'KSh 1,234.50'."""
    try:
        amount = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError):
        return value
    places = int(decimals)
    quant = Decimal(1).scaleb(-places) if places else Decimal(1)
    amount = amount.quantize(quant, rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    return f"{sign}KSh {abs(amount):,.{places}f}"


@register.filter
def clamp_pct(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return int(max(0, min(100, number)))


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def keylabel(value):
    """'days_of_history' -> 'Days of history'."""
    text = str(value).replace("_", " ").strip()
    return text[:1].upper() + text[1:]
