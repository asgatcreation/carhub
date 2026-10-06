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
