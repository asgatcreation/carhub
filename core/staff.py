"""Staff console: a branded front-end for moderators (listings, reviews, photos, verifications).

The Django admin stays available to superusers for raw data work; day-to-day moderation happens here.
"""
import re
from datetime import timedelta

from allauth.account.forms import LoginForm
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from cars.models import Car, CarImage, OrderItem
from cas.models import Product
from cas.models import Review as PartReview
from core.emails import send_branded
from users.models import Application, Notification, Review

CONTACT_RE = re.compile(r'(\+?\d[\d\s-]{8,}\d)|(https?://|www\.)|([\w.+-]+@[\w-]+\.\w+)', re.I)


def _ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _notify(user, actor, verb, message, link, subject, cta_label='Open CarHub'):
    if not user:
        return
    Notification.objects.create(user=user, actor=actor, verb=verb, message=message, link=link)
    send_branded(user.email, subject, heading=subject, body=message, cta_url=link, cta_label=cta_label)


def queue_counts():
    """Numbers shown in the console sidebar and overview."""
    return {
        'listings': Car.objects.filter(approval_status='pending').count(),
        'products': Product.objects.filter(status='pending').count(),
        'reviews': Review.objects.filter(status='pending').count() + PartReview.objects.filter(status='pending').count(),
        'photos': CarImage.objects.filter(reviewed_at__isnull=True, car__approval_status='approved').count(),
        'verifications': Application.objects.filter(status='pending').count(),
    }


# ---------------------------------------------------------------- sign in

def staff_login(request):
    """Branded sign-in for the console. Only staff accounts are let through."""
    nxt = request.GET.get('next') or request.POST.get('next') or reverse('staff:overview')
    if not url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        nxt = reverse('staff:overview')
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(nxt)

    form = LoginForm(request.POST or None, request=request)
    if request.method == 'POST' and form.is_valid():
        if not form.user.is_staff:
            form.add_error(None, "This account doesn't have staff access. Use the regular sign-in instead.")
        else:
            return form.login(request, redirect_url=nxt)
    demo_staff = None
    if settings.SHOW_DEMO_LOGINS:
        from cars.management.commands.seed_demo import DEMO_DOMAIN, DEMO_PASSWORD
        demo_staff = {'email': f'moderator@{DEMO_DOMAIN}', 'password': DEMO_PASSWORD}
    return render(request, 'staff/login.html', {'form': form, 'next': nxt, 'demo_staff': demo_staff})


# ---------------------------------------------------------------- overview

@staff_member_required
def overview(request):
    now = timezone.now()
    active = OrderItem.objects.filter(status__in=['reserved', 'scheduled'])
    counts = queue_counts()
    oldest = Car.objects.filter(approval_status='pending').order_by('created_at').first()

    events = []
    for car in Car.objects.select_related('created_by').order_by('-created_at')[:6]:
        events.append((car.created_at, 'car', f'{car.created_by.get_full_name() if car.created_by else "Someone"} listed {car.full_title}',
                       car.get_absolute_url()))
    for item in OrderItem.objects.exclude(status='awaiting_payment').select_related('order__user').order_by('-updated_at')[:6]:
        label = {'reserved': 'reserved', 'scheduled': 'booked an inspection for', 'completed': 'bought',
                 'cancelled': 'cancelled a reservation for'}[item.status]
        events.append((item.updated_at, item.status, f'{item.order.full_name} {label} {item.title}', ''))
    for review in Review.objects.select_related('reviewer', 'profile__user').order_by('-created_at')[:4]:
        events.append((review.created_at, 'review', f'{review.reviewer.get_full_name() if review.reviewer else "A buyer"} reviewed '
                       f'{review.profile.display_name} ({int(review.rating)}★)', reverse('staff:reviews')))
    events.sort(key=lambda e: e[0], reverse=True)

    hour = timezone.localtime(now).hour
    return render(request, 'staff/overview.html', {
        'section': 'overview',
        'greeting': 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening',
        'counts': counts,
        'todo': sum(counts.values()),
        'oldest': oldest,
        'pulse': {
            'live': Car.objects.public().count(),
            'reservations': active.count(),
            'deposits': active.aggregate(s=Sum('deposit'))['s'] or 0,
            'sold_30d': OrderItem.objects.filter(status='completed', completed_at__gte=now - timedelta(days=30)).count(),
            'new_users_7d': get_user_model().objects.filter(date_joined__gte=now - timedelta(days=7)).count(),
            'users': get_user_model().objects.count(),
        },
        'events': events[:10],
    })


# ---------------------------------------------------------------- reviews

def _flag(r, text):
    r.flags = []
    if CONTACT_RE.search(text):
        r.flags.append(('danger', 'Contains contact details or a link'))
    if len(r.body) < 25:
        r.flags.append(('warning', 'Very short'))
    if r.title and r.title.isupper():
        r.flags.append(('warning', 'Shouting'))


@staff_member_required
def reviews(request):
    """Seller reviews and product reviews share one queue, switched by ?kind=."""
    status = request.GET.get('status', 'pending')
    kind = 'parts' if request.GET.get('kind') == 'parts' else 'sellers'
    order = 'created_at' if status == 'pending' else '-moderated_at'
    if kind == 'sellers':
        items = list(Review.objects.filter(status=status).select_related('reviewer', 'profile__user').order_by(order)[:50])
        reviewer_ids = {r.reviewer_id for r in items if r.reviewer_id}
        written = dict(Review.objects.filter(reviewer_id__in=reviewer_ids).values_list('reviewer').annotate(n=Count('id')))
        bought = set(OrderItem.objects.filter(order__user_id__in=reviewer_ids, status='completed')
                     .values_list('order__user_id', 'seller_id'))
        for r in items:
            _flag(r, f'{r.title} {r.body}')
            r.author = r.reviewer
            r.subject_name = r.profile.display_name
            r.subject_url = reverse('cars:seller_profile', args=[r.profile.user_id])
            r.decide_url = reverse('staff:review_decide', args=[r.pk])
            r.verified_purchase = (r.reviewer_id, r.profile.user_id) in bought
            r.reviewer_total = written.get(r.reviewer_id, 0)
            r.sub_scores = [('Communication', r.communication), ('Professionalism', r.professionalism),
                            ('Punctuality', r.punctuality), ('Car as described', r.condition)]
        counts = dict(Review.objects.values_list('status').annotate(n=Count('id')))
    else:
        items = list(PartReview.objects.filter(status=status).select_related('user', 'product').order_by(order)[:50])
        written = dict(PartReview.objects.filter(user__in={r.user_id for r in items}).values_list('user').annotate(n=Count('id')))
        for r in items:
            _flag(r, f'{r.title} {r.body}')
            r.author = r.user
            r.subject_name = r.product.name
            r.subject_url = r.product.get_absolute_url()
            r.decide_url = reverse('staff:part_review_decide', args=[r.pk])
            r.reviewer_total = written.get(r.user_id, 0)
            r.sub_scores = []
        counts = dict(PartReview.objects.values_list('status').annotate(n=Count('id')))
    return render(request, 'staff/reviews.html', {
        'section': 'reviews', 'status': status, 'kind': kind, 'items': items, 'counts': counts,
        'pending_by_kind': {'sellers': Review.objects.filter(status='pending').count(),
                            'parts': PartReview.objects.filter(status='pending').count()},
        'reasons': ['Contains contact details or advertising', 'Not about a real purchase',
                    'Offensive or abusive language', 'Duplicate review'],
    })


@staff_member_required
@require_POST
def part_review_decide(request, review_id):
    review = get_object_or_404(PartReview.objects.select_related('user', 'product__vendor'), pk=review_id)
    decision = request.POST.get('decision')
    note = request.POST.get('reason', '').strip()[:300]
    if decision not in ('approve', 'reject') or (decision == 'reject' and not note):
        return HttpResponseBadRequest('decision and reason required')
    review.status = 'approved' if decision == 'approve' else 'rejected'
    review.moderated_by, review.moderated_at, review.moderation_note = request.user, timezone.now(), note
    review.save(update_fields=['status', 'moderated_by', 'moderated_at', 'moderation_note'])
    review.product.refresh_rating()
    url = f'{review.product.get_absolute_url()}#reviews'
    if decision == 'approve':
        _notify(review.user, request.user, 'review_published', f'Your review of {review.product.name} is now live.',
                url, 'Your review is published', 'See your review')
        _notify(review.product.vendor, review.user, 'review_received',
                f'{review.product.name} got a new {review.rating}-star review.', url, 'New product review', 'Read it')
    else:
        _notify(review.user, request.user, 'review_rejected',
                f'Your review of {review.product.name} was not published: {note} You can edit and resubmit it.',
                url, "Your review wasn't published", 'Edit review')
    if _ajax(request):
        return JsonResponse({'ok': True})
    return redirect(f"{reverse('staff:reviews')}?kind=parts")


# ---------------------------------------------------------------- parts store products

@staff_member_required
def products(request):
    status = request.GET.get('status', 'pending')
    qs = (Product.objects.filter(status=status).select_related('vendor__profile', 'category', 'brand')
          .prefetch_related('images', 'fitments', 'specs')
          .order_by('created_at' if status == 'pending' else '-moderated_at'))[:40]
    items = list(qs)
    for p in items:
        photos = len(p.images.all())
        fits = len(p.fitments.all())
        p.checks = [
            (photos >= 2, f'{photos} photo{"s" if photos != 1 else ""}'),
            (p.universal_fit or fits > 0, 'Universal fit' if p.universal_fit else f'{fits} compatible car range{"s" if fits != 1 else ""}'),
            (len(p.description) >= 80, 'Detailed description' if len(p.description) >= 80 else 'Short description'),
            (bool(p.sku) or p.part_type == 'accessory', 'Part number given' if p.sku else 'No part number'),
            (not CONTACT_RE.search(p.description), 'No contact details' if not CONTACT_RE.search(p.description) else 'Contact details in text'),
        ]
    return render(request, 'staff/products.html', {
        'section': 'products', 'status': status, 'items': items,
        'counts': dict(Product.objects.values_list('status').annotate(n=Count('id'))),
        'reasons': ['Photos are not of the actual product', 'Fitment list is missing or unclear',
                    'Price looks wrong', 'Contact details in the listing', 'Counterfeit or prohibited item'],
    })


@staff_member_required
@require_POST
def product_decide(request, product_id):
    p = get_object_or_404(Product.objects.select_related('vendor'), pk=product_id)
    decision = request.POST.get('decision')
    note = request.POST.get('reason', '').strip()[:300]
    if decision not in ('approve', 'reject') or (decision == 'reject' and not note):
        return HttpResponseBadRequest('decision and reason required')
    p.status = 'approved' if decision == 'approve' else 'rejected'
    p.moderated_by, p.moderated_at, p.moderation_note = request.user, timezone.now(), note
    p.save(update_fields=['status', 'moderated_by', 'moderated_at', 'moderation_note'])
    if decision == 'approve':
        _notify(p.vendor, request.user, 'product_approved', f'{p.name} is now live in the CarHub parts store.',
                p.get_absolute_url(), 'Your product is live', 'View product')
    else:
        _notify(p.vendor, request.user, 'product_rejected', f'{p.name} was not approved: {note}',
                reverse('cas:product_edit', args=[p.slug]), "Your product wasn't approved", 'Edit product')
    if _ajax(request):
        return JsonResponse({'ok': True})
    return redirect('staff:products')


@staff_member_required
@require_POST
def review_decide(request, review_id):
    review = get_object_or_404(Review.objects.select_related('reviewer', 'profile__user'), pk=review_id)
    decision = request.POST.get('decision')
    note = request.POST.get('reason', '').strip()[:300]
    if decision not in ('approve', 'reject') or (decision == 'reject' and not note):
        return HttpResponseBadRequest('decision and reason required')
    review.status = 'approved' if decision == 'approve' else 'rejected'
    review.moderated_by, review.moderated_at, review.moderation_note = request.user, timezone.now(), note
    review.save(update_fields=['status', 'moderated_by', 'moderated_at', 'moderation_note'])

    seller_url = reverse('cars:seller_profile', args=[review.profile.user_id])
    if decision == 'approve':
        _notify(review.reviewer, request.user, 'review_published',
                f'Your review of {review.profile.display_name} is now live. Thanks for helping other buyers.',
                f'{seller_url}#reviews', 'Your review is published', 'See your review')
        _notify(review.profile.user, review.reviewer, 'review_received',
                f'A buyer left you a {int(review.rating)}-star review.', f'{seller_url}#reviews',
                'You have a new review', 'Read it')
    else:
        _notify(review.reviewer, request.user, 'review_rejected',
                f'Your review of {review.profile.display_name} was not published: {note} You can edit and resubmit it.',
                f'{seller_url}#reviews', "Your review wasn't published", 'Edit review')
    if _ajax(request):
        return JsonResponse({'ok': True})
    messages.success(request, f'Review {review.get_status_display().lower()}.')
    return redirect('staff:reviews')


# ---------------------------------------------------------------- photos

@staff_member_required
def photos(request):
    items = (CarImage.objects.filter(reviewed_at__isnull=True, car__approval_status='approved')
             .select_related('car__created_by__profile').order_by('-created_at', '-pk')[:60])
    return render(request, 'staff/photos.html', {
        'section': 'photos', 'items': items,
        'reasons': ['Not the actual car', 'Contact details or watermark', 'Blurry or too dark', 'Inappropriate'],
    })


@staff_member_required
@require_POST
def photo_decide(request, image_id):
    image = get_object_or_404(CarImage.objects.select_related('car__created_by'), pk=image_id)
    decision = request.POST.get('decision')
    if decision == 'approve':
        image.reviewed_at, image.reviewed_by = timezone.now(), request.user
        image.save(update_fields=['reviewed_at', 'reviewed_by'])
    elif decision == 'reject':
        reason = request.POST.get('reason', '').strip()[:200] or 'It did not meet our photo guidelines.'
        car = image.car
        if image.image:
            image.image.delete(save=False)
        image.delete()
        _notify(car.created_by, request.user, 'photo_removed',
                f'We removed a photo from your listing "{car.full_title}". Reason: {reason}',
                reverse('cars:listing_edit', args=[car.slug]), 'A photo was removed from your listing', 'Update photos')
    else:
        return HttpResponseBadRequest('unknown decision')
    if _ajax(request):
        return JsonResponse({'ok': True})
    return redirect('staff:photos')


@staff_member_required
@require_POST
def photos_approve_all(request):
    ids = [int(i) for i in request.POST.getlist('ids') if i.isdigit()]
    n = CarImage.objects.filter(pk__in=ids, reviewed_at__isnull=True).update(reviewed_at=timezone.now(), reviewed_by=request.user)
    messages.success(request, f'{n} photo{"s" if n != 1 else ""} approved.')
    return redirect('staff:photos')


# ---------------------------------------------------------------- verifications

def _parse_vehicle(text):
    """'2019 Toyota Corolla, grey, LND-482-KJ' -> vehicle fields for a DriverProfile."""
    parts = [p.strip() for p in (text or '').split(',')]
    out = {}
    if parts and parts[0]:
        words = parts[0].split()
        if words and words[0].isdigit():
            out['vehicle_year'] = int(words.pop(0))
        if words:
            out['vehicle_make'] = words[0]
            out['vehicle_model'] = ' '.join(words[1:])
    if len(parts) > 1:
        out['vehicle_color'] = parts[1].title()[:30]
    if len(parts) > 2:
        out['plate_number'] = parts[2].upper()[:20]
    return out


ROLES = [('car_seller', 'Car dealers', 'verified'), ('pilot', 'Drivers', 'steering'), ('cas_seller', 'Accessory vendors', 'wrench')]


@staff_member_required
def verifications(request):
    role = request.GET.get('role', 'car_seller')
    if role not in dict((r, l) for r, l, _ in ROLES):
        role = 'car_seller'
    status = request.GET.get('status', 'pending')
    apps = (Application.objects.filter(role=role, status=status).select_related('user__profile')
            .annotate(listings=Count('user__cars_uploaded', distinct=True)).order_by('applied_at'))
    pending = dict(Application.objects.filter(status='pending').values_list('role').annotate(n=Count('id')))
    return render(request, 'staff/verifications.html', {
        'section': 'verifications', 'role': role, 'status': status, 'items': apps,
        'roles': [(r, label, icon, pending.get(r, 0)) for r, label, icon in ROLES],
        'role_label': dict((r, l) for r, l, _ in ROLES)[role],
    })


@staff_member_required
@require_POST
def verification_decide(request, app_id):
    app = get_object_or_404(Application.objects.select_related('user__profile'), pk=app_id, status='pending')
    decision = request.POST.get('decision')
    note = request.POST.get('reason', '').strip()[:300]
    if decision not in ('approve', 'reject', 'correction') or (decision != 'approve' and not note):
        return HttpResponseBadRequest('decision and reason required')
    app.status = {'approve': 'approved', 'reject': 'rejected', 'correction': 'correction_requested'}[decision]
    app.reviewed_by, app.reviewed_at = request.user, timezone.now()
    app.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    profile = app.user.profile
    what = {'car_seller': 'verified dealer', 'pilot': 'CarHub driver', 'cas_seller': 'accessory vendor'}[app.role]
    if decision == 'approve':
        if app.role == 'car_seller':
            profile.is_car_seller_approved = profile.is_verified = True
            if app.company_name and not profile.company_name:
                profile.company_name = app.company_name
        elif app.role == 'pilot':
            profile.is_pilot_approved = True
            from driverzone.models import DriverProfile
            vehicle = _parse_vehicle(app.vehicle_details)
            DriverProfile.objects.update_or_create(user=app.user, defaults={
                'license_number': app.id_number, 'license_verified': True, 'is_active': True,
                'years_experience': app.experience_years, 'city': profile.city or 'Lagos',
                'bio': app.additional_info[:500], **vehicle})
        else:
            profile.is_cas_seller_approved = True
        profile.save()
        message = f"You're now a {what} on CarHub." + (' Your listings go live instantly.' if app.role == 'car_seller' else '')
        _notify(app.user, request.user, 'application_approved', message, reverse('users:dashboard'),
                'Your verification was approved', 'Go to your dashboard')
    else:
        action = 'needs a few changes' if decision == 'correction' else 'was not approved'
        _notify(app.user, request.user, f'application_{app.status}', f'Your {what} application {action}: {note}',
                reverse('users:apply_seller'), f'Your verification {action}', 'Review application')
    if _ajax(request):
        return JsonResponse({'ok': True})
    messages.success(request, f'Application {app.get_status_display().lower()}.')
    return redirect(f"{reverse('staff:verifications')}?role={app.role}")


# ---------------------------------------------------------------- DriverZone live operations

@staff_member_required
def live_map(request):
    from driverzone.models import DriverProfile, Trip
    return render(request, 'staff/live.html', {
        'section': 'live',
        'today_trips': Trip.objects.filter(created_at__date=timezone.localdate()).count(),
        'drivers_total': DriverProfile.objects.filter(license_verified=True, is_active=True).count(),
    })


@staff_member_required
def live_data(request):
    from driverzone.services import ops_snapshot
    return JsonResponse(ops_snapshot())
