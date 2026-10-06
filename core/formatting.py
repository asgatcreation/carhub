"""Formatting helpers shared by models, views and templates."""
from decimal import Decimal, InvalidOperation


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def naira(value):
    """₦24,500,000 (drops kobo when the amount is whole)."""
    amount = _to_decimal(value)
    if amount is None:
        return '₦0'
    if amount == amount.to_integral():
        return f'₦{int(amount):,}'
    return f'₦{amount:,.2f}'


def naira_compact(value):
    """₦24.5M / ₦850K — for cards and chips."""
    amount = _to_decimal(value)
    if amount is None:
        return '₦0'
    for size, suffix in ((Decimal(1_000_000_000), 'B'), (Decimal(1_000_000), 'M'), (Decimal(1_000), 'K')):
        if abs(amount) >= size:
            short = (amount / size).quantize(Decimal('0.01'))
            text = f'{short:f}'.rstrip('0').rstrip('.')
            return f'₦{text}{suffix}'
    return f'₦{int(amount):,}'
