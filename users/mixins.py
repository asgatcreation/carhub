from django.core.exceptions import PermissionDenied


class RoleRequiredMixin:
    """Mixin for class-based views to require a specific role.

    Usage:
        class SellerView(RoleRequiredMixin, TemplateView):
            required_role = 'car_seller'
    """
    required_role = None

    def dispatch(self, request, *args, **kwargs):
        role = getattr(self, 'required_role', None)
        if role is None:
            return super().dispatch(request, *args, **kwargs)
        # Lazy import to avoid circular deps
        from .decorators import ROLE_MAP
        checker = ROLE_MAP.get(role)
        if not checker or not checker(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
