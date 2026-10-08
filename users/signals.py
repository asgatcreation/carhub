from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from .models import Message, Notification, Profile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Message)
def on_new_message(sender, instance, created, **kwargs):
    """Bump the conversation, notify the other participants and track seller response stats."""
    if not created:
        return
    convo = instance.conversation
    convo.save(update_fields=['updated_at'])

    sender_name = instance.sender.get_full_name() or instance.sender.email
    link = reverse('users:conversation', kwargs={'convo_id': convo.pk})
    for user in convo.participants.exclude(pk=instance.sender_id):
        Notification.objects.create(
            user=user, actor=instance.sender, verb='message',
            message=f'New message from {sender_name}', link=link,
        )

    _record_response(instance)


def _record_response(message):
    """Count a reply as a 'response' the first time a participant answers the other side."""
    convo = message.conversation
    previous = convo.messages.filter(created_at__lt=message.created_at).order_by('-created_at')
    last_other = previous.exclude(sender=message.sender).first()
    if not last_other:
        return
    already_replied = previous.filter(sender=message.sender, created_at__gt=last_other.created_at).exists() or \
        previous.filter(sender=message.sender).exists()
    if already_replied:
        return
    profile = getattr(message.sender, 'profile', None)
    if not profile:
        return
    count = profile.responses_count or 0
    delta = int((message.created_at - last_other.created_at).total_seconds())
    profile.avg_response_seconds = int(((profile.avg_response_seconds or 0) * count + delta) / (count + 1))
    profile.responses_count = count + 1
    profile.save(update_fields=['responses_count', 'avg_response_seconds'])


@receiver(pre_save, sender='cars.Car')
def count_completed_sale(sender, instance, **kwargs):
    """When a listing moves to 'sold', credit the seller's sales counters."""
    if not instance.pk or instance.status != 'sold' or not instance.created_by_id:
        return
    previous = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
    if previous == 'sold':
        return
    Profile.objects.filter(user_id=instance.created_by_id).update(
        sold_count=F('sold_count') + 1,
        completed_transactions=F('completed_transactions') + 1,
    )


@receiver(user_logged_in)
def merge_session_cart(sender, request, user, **kwargs):
    """Move a guest's session cart and wishlist into their account after login."""
    from cars.services import merge_session_into_account
    merge_session_into_account(request, user)
    from cas.services import merge_session_into_account as merge_parts
    merge_parts(request, user)
