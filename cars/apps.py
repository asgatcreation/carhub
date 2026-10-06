from django.apps import AppConfig


class CarsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cars'
    def ready(self):
        # Import signals to ensure they are registered when app is ready
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
