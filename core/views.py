from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.mail import mail_admins
from django.db.models import Count, Min
from django.shortcuts import redirect, render

from cars import services
from cars.models import BODY_TYPE_CHOICES, Car
from users.models import Profile


def home(request):
    public = Car.objects.public().select_related('created_by__profile').prefetch_related('images')
    body_counts = dict(public.values_list('body_type').annotate(n=Count('id')))
    body_from = dict(public.values_list('body_type').annotate(p=Min('price')))
    featured = list(public.filter(featured=True).order_by('?')[:8])
    latest = list(public.order_by('-created_at')[:8])
    recent = services.recently_viewed(request, limit=4)
    services.annotate_insights(featured + latest + recent)
    deals = [c for c in services.annotate_insights(list(public.filter(status='available')))
             if c.insight and c.insight['level'] in ('great', 'good')]
    deals.sort(key=lambda c: c.insight['pct'])
    return render(request, 'core/home.html', {
        'featured': featured,
        'spotlight': [c for c in featured if c.primary_image][:4],
        'latest': latest,
        'deals': deals[:4],
        'body_types': [(key, label, body_counts.get(key, 0), body_from.get(key)) for key, label in BODY_TYPE_CHOICES
                       if body_counts.get(key)],
        'brands': public.values('brand').annotate(n=Count('id')).order_by('-n')[:12],
        'all_brands': public.values('brand').annotate(n=Count('id')).order_by('brand'),
        'stats': {
            'listings': public.count(),
            'sellers': Profile.objects.filter(is_verified=True).count(),
            'states': public.values('state').distinct().count(),
        },
        'recent': recent,
        'saved_ids': set(services.wishlist_car_ids(request)),
        'parts': _popular_parts(),
    })


def _popular_parts():
    from cas.models import Category, Product
    items = list(Product.objects.public().filter(stock__gt=0).select_related('brand', 'category')
                 .prefetch_related('images', 'fitments').order_by('-sold_count')[:4])
    return {'items': items, 'categories': Category.objects.all()[:6], 'count': Product.objects.public().count()}


def about(request):
    return render(request, 'core/about.html', {
        'listings': Car.objects.public().count(),
        'sellers': Profile.objects.filter(is_verified=True).count(),
    })


class ContactForm(forms.Form):
    TOPICS = [('buying', 'Buying a car'), ('selling', 'Selling a car'), ('order', 'An existing order'), ('other', 'Something else')]
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    topic = forms.ChoiceField(choices=TOPICS)
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}), min_length=10, max_length=3000)


def contact(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {'name': request.user.get_full_name(), 'email': request.user.email}
    form = ContactForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        mail_admins(f"[{settings.SITE_NAME}] {dict(ContactForm.TOPICS)[data['topic']]} — {data['name']}",
                    f"From: {data['name']} <{data['email']}>\n\n{data['message']}", fail_silently=True)
        messages.success(request, "Thanks — we've received your message and will reply within one working day.")
        return redirect('contact')
    return render(request, 'core/contact.html', {'form': form})


def page_not_found(request, exception):
    return render(request, '404.html', status=404)


def server_error(request):
    return render(request, '500.html', status=500)
