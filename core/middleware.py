class PermissionsPolicyMiddleware:
    """Browser feature permissions: location only for this site (ride booking, driver app); nothing else."""
    POLICY = 'geolocation=(self), camera=(), microphone=(), payment=(self), usb=(), interest-cohort=()'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', self.POLICY)
        return response
