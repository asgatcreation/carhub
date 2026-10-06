

from django.shortcuts import render, get_object_or_404, redirect
from .models import Driver, Ride, Service, DriverReview
from .forms import RideOrderForm, DriverReviewForm, PilotApplicationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

def home_view(request):
    # Simple filters: q (search by name), available (1 or 0)
    q = request.GET.get('q', '').strip()
    available = request.GET.get('available', '1')
    drivers = Driver.objects.all()
    if available == '1':
        drivers = drivers.filter(is_available=True)
    if q:
        drivers = drivers.filter(user__username__icontains=q) | drivers.filter(user__first_name__icontains=q) | drivers.filter(user__last_name__icontains=q)
    services = Service.objects.all()
    context = {
        'drivers': drivers,
        'services': services,
        'q': q,
        'available': available,
    }
    return render(request, 'driverzone/home.html', context)

def driver_detail(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    reviews = driver.reviews.select_related('user').all()
    review_form = None
    review_submitted = False
    if request.user.is_authenticated:
        if request.method == 'POST' and 'review_submit' in request.POST:
            review_form = DriverReviewForm(request.POST)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.user = request.user
                review.driver = driver
                review.save()
                review_submitted = True
        else:
            review_form = DriverReviewForm()
    context = {
        'driver': driver,
        'reviews': reviews,
        'review_form': review_form,
        'review_submitted': review_submitted,
    }
    # expose drivers_list for partial include (keeps partial API simple)
    context['drivers_list'] = [driver]
    return render(request, 'driverzone/driver_detail.html', context)

@login_required
def order_driver(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    order_form = None
    order_submitted = False
    if request.method == 'POST':
        order_form = RideOrderForm(request.POST)
        if order_form.is_valid():
            ride = order_form.save(commit=False)
            ride.user = request.user
            ride.driver = driver
            ride.save()
            order_submitted = True
            # redirect to confirmation page
            messages.success(request, 'Ride requested — check My Rides for updates.')
            return redirect('driverzone:order_confirmation', pk=ride.pk)
    else:
        order_form = RideOrderForm()
    return render(request, 'driverzone/order_driver.html', {'driver': driver, 'order_form': order_form, 'order_submitted': order_submitted})


@login_required
def order_confirmation(request, pk):
    ride = get_object_or_404(Ride, pk=pk, user=request.user)
    return render(request, 'driverzone/order_confirmation.html', {'ride': ride})

@login_required
def my_rides(request):
    rides = Ride.objects.filter(user=request.user)
    return render(request, 'driverzone/my_rides.html', {'rides': rides})


@login_required
def update_ride_status(request, pk):
    # driver or owner can update ride status
    ride = get_object_or_404(Ride, pk=pk)
    # only driver assigned or staff can change status
    if request.user != (ride.driver.user if ride.driver else None) and not request.user.is_staff:
        messages.error(request, 'Permission denied to update this ride.')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'permission_denied'}, status=403)
        return redirect('driverzone:my_rides')
    new_status = request.POST.get('status')
    if new_status in dict(Ride.STATUS_CHOICES):
        ride.status = new_status
        ride.save()
        messages.success(request, 'Ride status updated.')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'status': ride.status})
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': False, 'error': 'invalid_status'}, status=400)
    return redirect('driverzone:order_confirmation', pk=ride.pk)


@login_required
def accept_ride(request, pk):
    # driver accepts an assigned ride
    ride = get_object_or_404(Ride, pk=pk)
    if request.user != (ride.driver.user if ride.driver else None) and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'permission_denied'}, status=403)
    if request.method == 'POST':
        ride.status = 'accepted'
        ride.save()
        return JsonResponse({'ok': True, 'status': ride.status})
    return JsonResponse({'ok': False, 'error': 'invalid_method'}, status=405)


@login_required
def decline_ride(request, pk):
    ride = get_object_or_404(Ride, pk=pk)
    if request.user != (ride.driver.user if ride.driver else None) and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'permission_denied'}, status=403)
    if request.method == 'POST':
        ride.status = 'declined'
        ride.save()
        return JsonResponse({'ok': True, 'status': ride.status})
    return JsonResponse({'ok': False, 'error': 'invalid_method'}, status=405)


@login_required
def assigned_rides(request):
    # Drivers can see rides assigned to them
    try:
        driver = request.user.driver_profile
    except Driver.DoesNotExist:
        return redirect('driverzone:profile')
    rides = Ride.objects.filter(driver=driver).order_by('-created_at')
    return render(request, 'driverzone/assigned_rides.html', {'rides': rides})


@login_required
def publish_driver(request, pk):
    # allow driver owners (the user linked to driver) to publish/unpublish their profile
    driver = get_object_or_404(Driver, pk=pk)
    if request.user != driver.user and not request.user.is_staff:
        messages.error(request, 'Permission denied.')
        return redirect('driverzone:driver_detail', pk=driver.pk)
    driver.is_available = not driver.is_available
    driver.save()
    messages.success(request, 'Availability toggled.')
    return redirect('driverzone:driver_detail', pk=driver.pk)

@login_required
def profile(request):
    return render(request, 'driverzone/profile.html')

@login_required
def apply_pilot(request):
    application_form = None
    application_submitted = False
    if request.method == 'POST':
        application_form = PilotApplicationForm(request.POST, request.FILES)
        if application_form.is_valid():
            pilot = application_form.save(commit=False)
            pilot.user = request.user
            pilot.save()
            application_submitted = True
    else:
        application_form = PilotApplicationForm()
    return render(request, 'driverzone/apply_pilot.html', {'application_form': application_form, 'application_submitted': application_submitted})


@login_required
def toggle_availability(request):
    # Allow drivers to toggle their availability from profile
    try:
        driver = request.user.driver_profile
    except Driver.DoesNotExist:
        return redirect('driverzone:profile')
    driver.is_available = not driver.is_available
    driver.save()
    return redirect('driverzone:profile')
