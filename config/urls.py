from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from django.views.generic import RedirectView

from django.contrib.sitemaps.views import sitemap

from core import views as core_views
from core.sitemaps import SITEMAPS
from users.views_auth import CarHubPasswordResetView

admin.site.site_header = 'CarHub administration'
admin.site.site_title = 'CarHub admin'
admin.site.index_title = 'Marketplace management'

urlpatterns = [
    path('', core_views.home, name='home'),
    path('about/', core_views.about, name='about'),
    path('contact/', core_views.contact, name='contact'),
    path('terms/', core_views.terms, name='terms'),
    path('privacy/', core_views.privacy, name='privacy'),
    path('offline/', core_views.offline, name='offline'),
    path('healthz/', core_views.healthz, name='healthz'),
    path('robots.txt', core_views.robots_txt, name='robots'),
    path('sw.js', core_views.service_worker, name='service_worker'),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='django.contrib.sitemaps.views.sitemap'),
    path('accessories/', include('cas.urls')),
    path('drivers/', include('driverzone.urls')),

    path('cars/', include('cars.urls')),
    # Forgot password knows about Google-only accounts (must come before allauth's URLs).
    path('accounts/password/reset/', CarHubPasswordResetView.as_view(), name='account_reset_password'),
    path('accounts/', include('allauth.urls')),
    path('account/', include('users.urls')),
    path('staff/', include('core.staff_urls')),
    # Every staff sign-in (including Django admin's) goes through the branded console login.
    path('admin/login/', RedirectView.as_view(pattern_name='staff:login', query_string=True)),
    path('admin/', admin.site.urls),

    # Old URLs kept as redirects
    path('cas/', RedirectView.as_view(pattern_name='cas:home')),
    path('driverzone/', RedirectView.as_view(pattern_name='driverzone:home')),
    path('users/', RedirectView.as_view(pattern_name='users:dashboard')),
    path('users/<path:rest>', RedirectView.as_view(url='/account/%(rest)s')),
    path('login/', RedirectView.as_view(pattern_name='account_login')),
    path('cars/about/team/', RedirectView.as_view(pattern_name='about')),
    path('cars/about/mission/', RedirectView.as_view(pattern_name='about')),
    path('cars/about/vision/', RedirectView.as_view(pattern_name='about')),
    path('cars/contact-us/', RedirectView.as_view(pattern_name='contact')),
]

handler404 = 'core.views.page_not_found'
handler500 = 'core.views.server_error'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    # Demo-scale hosting without object storage: let Django serve uploaded photos.
    urlpatterns += [re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT})]
