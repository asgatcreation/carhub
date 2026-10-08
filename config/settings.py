"""
Django settings for CarHub.

All secrets and environment-specific values come from environment variables
(loaded from a local `.env` file in development — see `.env.example`).
"""
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [v.strip() for v in os.environ.get(name, default).split(',') if v.strip()]


# ======================
# CORE / SECURITY
# ======================

DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.')
    SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production'

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# Render (and similar hosts) expose the public hostname; trust it automatically.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

# Absolute base URL for links inside emails (which are rendered outside a request).
# DriverZone demo trips run this many times faster than real time so a trip finishes in a couple of minutes.
DRIVERZONE_SIM_SPEED = int(os.environ.get('DRIVERZONE_SIM_SPEED', '10'))

SITE_URL = (os.environ.get('SITE_URL') or (f'https://{RENDER_EXTERNAL_HOSTNAME}' if RENDER_EXTERNAL_HOSTNAME else 'http://localhost:8000')).rstrip('/')

# ======================
# APPLICATIONS
# ======================

INSTALLED_APPS = [
    'daphne',  # runserver serves WebSockets too (live tracking, chat, notifications)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    'django.contrib.sitemaps',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    'core',
    'cars',
    'users',
    'cas',
    'driverzone',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.PermissionsPolicyMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'core.context_processors.cart',
                'core.context_processors.site_settings',
                'core.context_processors.demo_logins',
                'users.context_processors.notifications_processor',
                'core.context_processors.staff_console',
            ],
            'builtins': ['core.templatetags.ui'],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ======================
# DATABASE
# ======================
# SQLite locally; set DATABASE_URL=postgres://user:pass@host:5432/name in production.

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    _db = urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _db.path.lstrip('/'),
            'USER': _db.username or '',
            'PASSWORD': _db.password or '',
            'HOST': _db.hostname or '',
            'PORT': str(_db.port or 5432),
            'CONN_MAX_AGE': 60,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'carhub',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ======================
# I18N
# ======================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

# ======================
# STATIC & MEDIA
# ======================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
        else 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Serve uploads from Django when DEBUG is off (fine for a demo; use S3/Cloudinary at scale).
SERVE_MEDIA = env_bool('SERVE_MEDIA', True)

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_IMAGE_UPLOAD_MB = 8

# ======================
# AUTH (django-allauth)
# ======================

SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_SIGNUP_FORM_CLASS = 'users.signup_form.CustomSignupForm'
ACCOUNT_USER_DISPLAY = lambda user: user.get_full_name() or user.email
ACCOUNT_EMAIL_SUBJECT_PREFIX = ''
ACCOUNT_ADAPTER = 'users.adapter.AccountAdapter'
# Say plainly when an email has no account (forgot password / sign up). Rate limits still apply.
ACCOUNT_PREVENT_ENUMERATION = False
ACCOUNT_EMAIL_NOTIFICATIONS = True                    # 'your password was changed' security emails

# One-time codes instead of links: a 6-character code is emailed to verify a new
# account, and another to reset a forgotten password. The code is only in the body.
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT = 15 * 60
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_TIMEOUT = 10 * 60
ACCOUNT_PASSWORD_RESET_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = '/'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http' if DEBUG else 'https'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        **({'APP': {'client_id': GOOGLE_CLIENT_ID, 'secret': GOOGLE_CLIENT_SECRET}} if GOOGLE_CLIENT_ID else {}),
    },
}
SOCIAL_LOGIN_ENABLED = bool(GOOGLE_CLIENT_ID)
SOCIALACCOUNT_AUTO_SIGNUP = True                      # Google gives us name + verified email: no extra form
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True             # "Continue with Google" also signs in existing email accounts
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_LOGIN_ON_GET = False                    # the button POSTs (CSRF-safe) straight to Google

# ======================
# EMAIL
# ======================

EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').replace(' ', '')  # Gmail app passwords are shown with spaces
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_TIMEOUT = 15
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')

# Pick the first transport that is configured: Brevo's HTTP API (works on hosts that
# block outbound SMTP), then SMTP (e.g. Gmail with an app password), else print to console.
if os.environ.get('EMAIL_BACKEND'):
    EMAIL_BACKEND = os.environ['EMAIL_BACKEND']
elif BREVO_API_KEY:
    EMAIL_BACKEND = 'core.email_backends.BrevoEmailBackend'
elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_ENABLED = EMAIL_BACKEND != 'django.core.mail.backends.console.EmailBackend'

# Require the emailed code before a new account can sign in, but only when mail can
# actually be delivered; otherwise a fresh deploy without SMTP would lock everyone out.
ACCOUNT_EMAIL_VERIFICATION = os.environ.get('ACCOUNT_EMAIL_VERIFICATION', 'mandatory' if EMAIL_ENABLED else 'optional')
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = ACCOUNT_EMAIL_VERIFICATION == 'mandatory'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL') or (f'CarHub <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER else 'CarHub <noreply@carhub.local>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ======================
# SESSIONS
# ======================

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True

# ======================
# REAL-TIME (Channels)
# ======================

# Set when serving through an ASGI server (daphne/uvicorn); otherwise chat falls back to HTTP polling.
CHAT_WEBSOCKETS = env_bool('CHAT_WEBSOCKETS', True)  # daphne serves WebSockets in dev (runserver) and production
REDIS_URL = os.environ.get('REDIS_URL', '')
CHANNEL_LAYERS = {
    'default': (
        {'BACKEND': 'channels_redis.core.RedisChannelLayer', 'CONFIG': {'hosts': [REDIS_URL]}}
        if REDIS_URL else {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
    )
}

# ======================
# LOGGING
# ======================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '{levelname} {name}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'), 'propagate': False},
        'carhub': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ======================
# CARHUB SETTINGS
# ======================

SITE_NAME = 'CarHub'
SITE_DESCRIPTION = 'Buy and sell verified cars across Nigeria'
CURRENCY = 'NGN'
CURRENCY_SYMBOL = '₦'

ITEMS_PER_PAGE = 12
CAR_SELLER_COMMISSION = 0.05
# Refundable deposit (₦) charged online to reserve a car; the balance is paid after inspection.
CAR_RESERVATION_DEPOSIT = int(os.environ.get('CAR_RESERVATION_DEPOSIT', '250000'))

# Payments: Paystack test/live secret key. Without a key, checkout only works
# when DEMO_CHECKOUT is on (orders are recorded and clearly marked as demo).
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', '')
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
DEMO_CHECKOUT = env_bool('DEMO_CHECKOUT', DEBUG)
# Show one-click demo accounts on the sign-in page (for portfolio reviewers).
SHOW_DEMO_LOGINS = env_bool('SHOW_DEMO_LOGINS', DEBUG)

# ======================
# PRODUCTION HARDENING
# ======================

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

# Serve the PWA manifest with its registered type (WhiteNoise uses mimetypes).
mimetypes.add_type('application/manifest+json', '.webmanifest')
