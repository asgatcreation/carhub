from django.urls import path

from . import staff

app_name = 'staff'

urlpatterns = [
    path('', staff.overview, name='overview'),
    path('login/', staff.staff_login, name='login'),
    path('reviews/', staff.reviews, name='reviews'),
    path('reviews/<int:review_id>/', staff.review_decide, name='review_decide'),
    path('part-reviews/<int:review_id>/', staff.part_review_decide, name='part_review_decide'),
    path('products/', staff.products, name='products'),
    path('products/<int:product_id>/', staff.product_decide, name='product_decide'),
    path('photos/', staff.photos, name='photos'),
    path('photos/approve-all/', staff.photos_approve_all, name='photos_approve_all'),
    path('photos/<int:image_id>/', staff.photo_decide, name='photo_decide'),
    path('verifications/', staff.verifications, name='verifications'),
    path('verifications/<int:app_id>/', staff.verification_decide, name='verification_decide'),
]
