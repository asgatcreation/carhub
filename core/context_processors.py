from django.conf import settings

from cars import services


def cart(request):
    """Cart and saved-car counts for the header badges."""
    if request.path.startswith(('/admin/', '/static/', '/media/')):
        return {}
    return {
        'cart_count': len(services.cart_car_ids(request)),
        'saved_count': len(services.wishlist_car_ids(request)),
    }


def site_settings(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_DESCRIPTION': settings.SITE_DESCRIPTION,
        'SOCIAL_LOGIN_ENABLED': settings.SOCIAL_LOGIN_ENABLED,
        'DEMO_CHECKOUT': settings.DEMO_CHECKOUT,
        'CHAT_WEBSOCKETS': settings.CHAT_WEBSOCKETS,
    }


def demo_logins(request):
    """Demo accounts for the sign-in page (only when SHOW_DEMO_LOGINS is on)."""
    if not settings.SHOW_DEMO_LOGINS or not request.path.startswith('/accounts/login'):
        return {}
    from cars.management.commands.seed_demo import DEMO_DOMAIN, DEMO_PASSWORD
    return {'demo_logins': {
        'password': DEMO_PASSWORD,
        'accounts': [
            ('Buyer', f'buyer@{DEMO_DOMAIN}', 'Orders, saved cars & messages'),
            ('Dealer', f'harborpoint@{DEMO_DOMAIN}', 'Verified dealer with listings'),
            ('Moderator', f'moderator@{DEMO_DOMAIN}', 'Review the listing queue'),
        ],
    }}


def staff_console(request):
    """Queue sizes for the staff console sidebar (only computed on console pages)."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_staff):
        return {}
    if not request.path.startswith(('/staff/', '/cars/moderation')):
        return {'is_staff_user': True}
    from core.staff import queue_counts
    return {'is_staff_user': True, 'queue': queue_counts()}
