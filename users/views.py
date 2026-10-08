from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from cars.models import Car

from .forms import AccountForm, ProfileForm, SellerApplicationForm
from .models import Application, Conversation, Message, Notification


@login_required
def dashboard(request):
    user = request.user
    listings = Car.objects.by_seller(user)
    return render(request, 'users/dashboard.html', {
        'recent_orders': user.orders.prefetch_related('items')[:3],
        'order_count': user.orders.count(),
        'saved_count': user.wishlist_items.count(),
        'listing_stats': {
            'live': listings.filter(approval_status='approved', status='available').count(),
            'pending': listings.filter(approval_status='pending').count(),
            'total': listings.count(),
        },
        'unread_messages': Message.objects.filter(conversation__participants=user, read=False).exclude(sender=user).count(),
        'recent_notifications': user.notifications.all()[:5],
        'application': Application.objects.filter(user=user, role='car_seller').order_by('-applied_at').first(),
    })


@login_required
def settings_view(request):
    profile = request.user.profile
    account_form = AccountForm(request.POST or None, instance=request.user)
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST' and account_form.is_valid() and profile_form.is_valid():
        account_form.save()
        profile_form.save()
        messages.success(request, 'Your profile has been updated.')
        return redirect('users:settings')
    return render(request, 'users/settings.html', {'account_form': account_form, 'profile_form': profile_form})


# ======================
# MESSAGES
# ======================

@login_required
def inbox(request):
    user = request.user
    convos = (user.conversations
              .select_related('car').prefetch_related('participants__profile', 'car__images')
              .annotate(last_at=Max('messages__created_at'),
                        unread=Count('messages', filter=Q(messages__read=False) & ~Q(messages__sender=user)))
              .filter(last_at__isnull=False).order_by('-last_at'))
    items = []
    for convo in convos:
        last = convo.messages.order_by('-created_at').first()
        items.append({'convo': convo, 'other': convo.other_participant(user), 'last': last})
    return render(request, 'users/inbox.html', {'items': items})


@login_required
def conversation(request, convo_id):
    convo = get_object_or_404(Conversation.objects.select_related('car'), pk=convo_id, participants=request.user)
    if request.method == 'POST':
        text = request.POST.get('content', '').strip()[:2000]
        if not text:
            return JsonResponse({'ok': False, 'error': 'Message is empty.'}, status=400)
        msg = Message.objects.create(conversation=convo, sender=request.user, content=text)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'message': _serialize(msg, request.user)})
        return redirect('users:conversation', convo_id=convo.pk)

    convo.messages.filter(read=False).exclude(sender=request.user).update(read=True)
    thread = list(convo.messages.select_related('sender').order_by('-created_at')[:300])[::-1]
    other = convo.other_participant(request.user)
    avg = getattr(getattr(other, 'profile', None), 'avg_response_seconds', 0)
    return render(request, 'users/conversation.html', {
        'convo': convo,
        'other': other,
        'thread': thread,
        'last_id': thread[-1].pk if thread else 0,
        'reply_minutes': max(1, round(avg / 60)) if avg else None,
    })


@login_required
@require_GET
def conversation_poll(request, convo_id):
    """New messages since `after` (message id) — used by the chat page when WebSockets are unavailable."""
    convo = get_object_or_404(Conversation, pk=convo_id, participants=request.user)
    after = int(request.GET.get('after') or 0)
    new = list(convo.messages.filter(pk__gt=after).select_related('sender'))
    convo.messages.filter(pk__gt=after, read=False).exclude(sender=request.user).update(read=True)
    return JsonResponse({'messages': [_serialize(m, request.user) for m in new]})


def _serialize(msg, viewer):
    return {
        'id': msg.pk,
        'content': msg.content,  # rendered with textContent on the client
        'mine': msg.sender_id == viewer.pk,
        'sender': msg.sender.get_full_name() or msg.sender.email,
        'time': timezone.localtime(msg.created_at).strftime('%H:%M'),
    }


# ======================
# NOTIFICATIONS
# ======================

@login_required
def notifications(request):
    notes = request.user.notifications.select_related('actor')[:100]
    response = render(request, 'users/notifications.html', {'notes': notes})
    request.user.notifications.filter(unread=True).update(unread=False)
    return response


@login_required
@require_POST
def notifications_mark_read(request):
    request.user.notifications.filter(unread=True).update(unread=False)
    return JsonResponse({'ok': True})


# ======================
# SELLER VERIFICATION
# ======================

@login_required
def apply_seller(request):
    existing = Application.objects.filter(user=request.user, role='car_seller').order_by('-applied_at').first()
    if request.user.profile.is_car_seller_approved:
        messages.info(request, "You're already a verified seller.")
        return redirect('users:dashboard')
    if existing and existing.status == 'pending':
        return render(request, 'users/apply.html', {'pending': existing})

    form = SellerApplicationForm(request.POST or None, request.FILES or None, initial={
        'full_name': request.user.get_full_name(), 'phone': request.user.profile.phone,
    })
    if request.method == 'POST' and form.is_valid():
        app = form.save(commit=False)
        app.user = request.user
        app.role = 'car_seller'
        app.save()
        messages.success(request, "Application received — we'll review it within 2 working days.")
        return redirect('users:dashboard')
    return render(request, 'users/apply.html', {'form': form})


@staff_member_required
def applications(request):
    """Moved to the staff console."""
    return redirect('staff:verifications')
