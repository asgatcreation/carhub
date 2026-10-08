"""Template helpers available in every template (registered as a builtin)."""
from django import template
from django.utils.html import format_html

from core.formatting import naira, naira_compact

register = template.Library()


@register.filter(name='naira')
def naira_filter(value):
    return naira(value)


@register.filter(name='naira_short')
def naira_short_filter(value):
    return naira_compact(value)


@register.filter
def km(value):
    try:
        return f'{int(value):,} km'
    except (TypeError, ValueError):
        return '—'


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Rebuild the current query string with some keys replaced (None/'' removes the key)."""
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f'?{encoded}' if encoded else '?'


@register.simple_tag
def icon(name, size=20, cls=''):
    """Inline SVG icon from the sprite in static/img/icons.svg."""
    return format_html(
        '<svg class="icon {}" width="{}" height="{}" aria-hidden="true"><use href="#i-{}"></use></svg>',
        cls, size, size, name,
    )


@register.filter
def initials(user):
    name = (getattr(user, 'get_full_name', lambda: '')() or getattr(user, 'email', '') or '?').strip()
    parts = [p for p in name.replace('@', ' ').split() if p]
    return ''.join(p[0] for p in parts[:2]).upper() or '?'


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def ago(value):
    """'3 hours ago' — only the largest unit of Django's timesince."""
    if not value:
        return ''
    from django.utils.timesince import timesince
    first = timesince(value).split(',')[0].replace('\xa0', ' ')
    return 'just now' if first.startswith('0 ') else f'{first} ago'


@register.filter
def monthly(price, months=36):
    """Indicative monthly repayment: 30% down, 24% APR over 36 months (matches the detail-page calculator)."""
    try:
        principal = float(price) * 0.7
    except (TypeError, ValueError):
        return ''
    rate = 0.24 / 12
    payment = principal * rate / (1 - (1 + rate) ** -int(months))
    return naira_compact(round(payment, -3))


@register.filter
def absval(value):
    try:
        return abs(value)
    except TypeError:
        return value


@register.filter
def split(value, sep=','):
    return [part.strip() for part in str(value).split(sep) if part.strip()]


@register.filter
def sub(value, arg):
    try:
        return value - arg
    except TypeError:
        return value


@register.filter
def fits_vehicle(fitment, vehicle):
    """True when a cas Fitment matches the garage vehicle dict."""
    return bool(vehicle) and fitment.matches(vehicle.get('make'), vehicle.get('model'), vehicle.get('year'))


@register.filter
def fits_garage(product, vehicle):
    """True / False / None: does a cas Product fit the garage vehicle?"""
    return product.fits(vehicle)


@register.filter
def map_attr(items, attr):
    return [getattr(i, attr) for i in items]


@register.filter
def absolutize(url, request):
    """Make a site-relative URL absolute (link previews need full URLs)."""
    url = str(url or '')
    return request.build_absolute_uri(url) if url.startswith('/') else url
