from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


ROLE_MAP = {
    'car_seller': lambda user: getattr(getattr(user, 'profile', None), 'is_car_seller_approved', False) or user.groups.filter(name='car_seller').exists(),
    'cas_seller': lambda user: getattr(getattr(user, 'profile', None), 'is_cas_seller_approved', False) or user.groups.filter(name='cas_seller').exists(),
    'pilot': lambda user: getattr(getattr(user, 'profile', None), 'is_pilot_approved', False) or user.groups.filter(name='pilot').exists(),
    'buyer': lambda user: True,
}


def role_required(role, login_url='/accounts/login/'):
    """Decorator that ensures the authenticated user has the given role.

    Role checks the `Profile` approval boolean and group membership.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not getattr(user, 'is_authenticated', False):
                return redirect(login_url)
            checker = ROLE_MAP.get(role)
            if checker and checker(user):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden('You do not have permission to access this resource.')
        return _wrapped
    return decorator
