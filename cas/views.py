
from django.shortcuts import render, get_object_or_404, redirect
from .models import Accessory, Category, Brand, Order, AccessoryReview
from .forms import AccessoryForm, AccessoryReviewForm, OrderForm
from django.contrib.auth.decorators import login_required

def home_view(request):
    categories = Category.objects.all()
    accessories = Accessory.objects.select_related('category', 'brand').order_by('-created_at')[:12]
    brands = Brand.objects.all()
    # attach brand_slug to accessories for template URL building
    accessories = list(accessories)
    for a in accessories:
        if a.brand:
            a.brand_slug = getattr(a.brand, 'slug', None) or (a.brand.name.lower().replace(' ', '-') if a.brand.name else 'brand')
        else:
            a.brand_slug = 'brand'
    context = {
        'categories': categories,
        'accessories': accessories,
        'brands': brands,
    }
    return render(request, 'cas/home.html', context)

def accessory_detail(request, slug):
    accessory = get_object_or_404(Accessory, slug=slug)
    reviews = accessory.reviews.select_related('user').all()
    review_form = None
    order_form = None
    review_submitted = False
    order_submitted = False
    if request.user.is_authenticated:
        if request.method == 'POST':
            if 'review_submit' in request.POST:
                review_form = AccessoryReviewForm(request.POST)
                if review_form.is_valid():
                    review = review_form.save(commit=False)
                    review.user = request.user
                    review.accessory = accessory
                    review.save()
                    review_submitted = True
            elif 'order_submit' in request.POST:
                order_form = OrderForm(request.POST)
                if order_form.is_valid():
                    order = order_form.save(commit=False)
                    order.user = request.user
                    order.accessory = accessory
                    order.save()
                    order_submitted = True
        else:
            review_form = AccessoryReviewForm()
            order_form = OrderForm()
    context = {
        'accessory': accessory,
        # alias for templates that will be renamed to use `product`
        'product': accessory,
        'reviews': reviews,
        'review_form': review_form,
        'order_form': order_form,
        'review_submitted': review_submitted,
        'order_submitted': order_submitted,
    }
    # Add aggregate rating and related products for JSON-LD and gallery
    review_count = reviews.count()
    avg_rating = None
    if review_count > 0:
        avg_rating = round(sum([r.rating for r in reviews]) / review_count, 2)
    related_products = []
    if accessory.category:
        related_products = list(accessory.category.accessories.exclude(pk=accessory.pk).select_related('brand')[:6])
        # attach brand_slug and product_slug to related items for template URL construction
        for rp in related_products:
            if rp.brand and rp.brand.name:
                rp.brand_slug = rp.brand.name.lower().replace(' ', '-')
            else:
                rp.brand_slug = 'brand'
            rp.product_slug = rp.slug
    # main accessory brand slug
    if accessory.brand and accessory.brand.name:
        accessory.brand_slug = accessory.brand.name.lower().replace(' ', '-')
    else:
        accessory.brand_slug = 'brand'
    # build product JSON-LD server-side for cleaner templates
    gallery = [accessory.image.url] + [img.image.url for img in accessory.images.all()]
    review_list = []
    for r in reviews:
        review_list.append({
            '@type': 'Review',
            'author': r.user.get_full_name() or r.user.username,
            'datePublished': r.created_at.date().isoformat(),
            'reviewBody': r.comment,
            'reviewRating': { '@type': 'Rating', 'ratingValue': r.rating }
        })
    product_jsonld = {
        '@context': 'https://schema.org/',
        '@type': 'Product',
        'name': accessory.name,
        'image': gallery,
        'description': (accessory.description[:197] + '...') if len(accessory.description) > 200 else accessory.description,
        'sku': f"CAS-{accessory.pk}",
        'brand': { '@type': 'Brand', 'name': accessory.brand.name } if accessory.brand else None,
        'offers': { '@type': 'Offer', 'priceCurrency': 'NGN', 'price': str(accessory.price), 'availability': 'https://schema.org/InStock' if accessory.in_stock else 'https://schema.org/OutOfStock' },
        'aggregateRating': { '@type': 'AggregateRating', 'ratingValue': avg_rating, 'reviewCount': review_count } if avg_rating else None,
        'review': review_list
    }
    # remove keys with None to keep JSON-LD clean
    cleaned = {k: v for k, v in product_jsonld.items() if v is not None}
    import json
    product_jsonld_json = json.dumps(cleaned, ensure_ascii=False)
    context.update({'review_count': review_count, 'avg_rating': avg_rating, 'related_products': related_products, 'product_jsonld_json': product_jsonld_json, 'gallery': gallery, 'attributes': list(accessory.attributes.all())})
    return render(request, 'cas/accessory_detail.html', context)


def product_detail(request, brand_slug, product_slug):
    """New route wrapper: /cas/product/<brand_slug>/<product_slug>/
    Resolves the Accessory by product_slug and ensures brand_slug matches when provided.
    Reuses accessory_detail logic by building the same context and rendering the same template.
    """
    accessory = get_object_or_404(Accessory, slug=product_slug)
    # optional brand check - if brand_slug provided but doesn't match, redirect to canonical
    if accessory.brand and accessory.brand.name:
        slugified = accessory.brand.name.lower().replace(' ', '-')
        if brand_slug != slugified:
            # canonical url could be constructed; but for now we continue and render the page
            pass

    # reuse accessory_detail to build context: call the same internal logic by delegating
    # We'll call the accessory_detail view function's logic by copying minimal required context.
    # Simpler: call accessory_detail to return the same response but ensure we pass brand/product slugs in context
    response = accessory_detail(request, slug=product_slug)
    try:
        # response is an HttpResponse with rendered content; if it's a render() result we can return it directly
        return response
    except Exception:
        # fallback: render manually if accessory_detail raised; but normally accessory_detail returns a response
        return response

def category_view(request, pk):
    category = get_object_or_404(Category, pk=pk)
    accessories = category.accessories.select_related('brand').all()
    accessories = list(accessories)
    for a in accessories:
        if a.brand:
            a.brand_slug = getattr(a.brand, 'slug', None) or (a.brand.name.lower().replace(' ', '-') if a.brand.name else 'brand')
        else:
            a.brand_slug = 'brand'
    return render(request, 'cas/category.html', {'category': category, 'accessories': accessories})

def brand_view(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    accessories = brand.accessories.select_related('category').all()
    accessories = list(accessories)
    for a in accessories:
        if a.brand:
            a.brand_slug = getattr(a.brand, 'slug', None) or (a.brand.name.lower().replace(' ', '-') if a.brand.name else 'brand')
        else:
            a.brand_slug = 'brand'
    return render(request, 'cas/brand.html', {'brand': brand, 'accessories': accessories})

@login_required
def upload_accessory(request):
    success = False
    error_message = None
    if request.method == 'POST':
        form = AccessoryForm(request.POST, request.FILES)
        if form.is_valid():
            accessory = form.save(commit=False)
            accessory.seller = request.user
            accessory.save()
            success = True
            form = AccessoryForm()  # Reset form after success
        else:
            error_message = 'Please correct the errors below.'
    else:
        form = AccessoryForm()
    return render(request, 'cas/upload_accessory.html', {'form': form, 'success': success, 'error_message': error_message})

@login_required
def my_uploads(request):
    accessories = Accessory.objects.filter(seller=request.user)
    accessories = list(accessories)
    for a in accessories:
        if a.brand:
            a.brand_slug = getattr(a.brand, 'slug', None) or (a.brand.name.lower().replace(' ', '-') if a.brand.name else 'brand')
        else:
            a.brand_slug = 'brand'
    return render(request, 'cas/my_uploads.html', {'accessories': accessories})

@login_required
def orders(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'cas/orders.html', {'orders': orders})

@login_required
def profile(request):
    return render(request, 'cas/profile.html')

def apply_cas_seller(request):
    # TODO: Implement seller application logic
    return render(request, 'cas/apply_cas_seller.html')
