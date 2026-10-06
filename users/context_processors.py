def notifications_processor(request):
    """Unread notification and message counts for the header."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated) or request.path.startswith(('/admin/', '/static/', '/media/')):
        return {}
    from .models import Message
    return {
        'notifications_unread_count': user.notifications.filter(unread=True).count(),
        'messages_unread_count': Message.objects.filter(conversation__participants=user, read=False).exclude(sender=user).count(),
        'active_reservations_count': user.sales.filter(status__in=['reserved', 'scheduled']).count(),
    }
