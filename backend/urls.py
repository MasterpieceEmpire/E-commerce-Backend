from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from megamall.views import (
    ProductView,
    CategoryView,
    HireItemViewSet,
    GuestUserViewSet,
    ShippingAddressViewSet,
    CustomTokenObtainPairView,
    user_profile,
    create_order,
    get_order_status,
    invoice_pdf_view,
    initiate_payment,
    create_courier_order,
    NoSignalLoginView,
)

# DRF Router (only for ViewSets)
router = DefaultRouter()
router.register(r'products', ProductView, basename='product')
router.register(r'categories', CategoryView, basename='category')
router.register(r'guest-users', GuestUserViewSet, basename='guestuser')
router.register(r'hire-items', HireItemViewSet, basename='hireitem')
router.register(r'shipping-addresses', ShippingAddressViewSet, basename='shippingaddress')

# URL Patterns
urlpatterns = [
    # Redirect root to API base
    path('', RedirectView.as_view(url='/api/', permanent=False)),

    # ✅ Custom Admin Login BEFORE default admin
    path('admin/login/', NoSignalLoginView.as_view(), name='login'),
    path('admin/', admin.site.urls),

    # API Base Routes from DRF router
    path('api/', include(router.urls)),

    # Authentication
    path('api/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # User
    path('api/user-profile/', user_profile, name='user-profile'),

    # Orders
    path('api/orders/', create_order, name='create-order'),
    path('api/orders/<uuid:order_id>/status/', get_order_status, name='order-status'),
    path('api/orders/<uuid:order_id>/invoice/', invoice_pdf_view, name='invoice-pdf'),

    # M-Pesa
    path('api/payment/mpesa/initiate/', initiate_payment, name='initiate-payment'),

    # Courier
    path('api/courier/', create_courier_order, name='create-courier-order'),

    # Fix urls command
    path('fix-urls/', fix_image_urls_view, name='fix_urls'),
]

# Static/media handling for development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
