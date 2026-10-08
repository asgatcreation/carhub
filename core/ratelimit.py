"""Tiny cache-based rate limiter for endpoints that cost money or hit external services."""
import time
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render


def client_key(request):
    if getattr(request, 'user', None) and request.user.is_authenticated:
        return f'u{request.user.pk}'
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return 'ip' + (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', ''))


def rate_limit(name, limit, per=60):
    """Allow `limit` calls per `per` seconds per user (or IP); beyond that answer 429."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            window = int(time.time() // per)
            key = f'rl:{name}:{client_key(request)}:{window}'
            count = cache.get_or_set(key, 0, per + 5)
            if count >= limit:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                    return JsonResponse({'error': 'Too many requests. Please wait a moment and try again.'}, status=429)
                return render(request, '429.html', status=429)
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, per + 5)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
