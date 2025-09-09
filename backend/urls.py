# urls.py

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
    upload_image,  
    test_mongo_connection,
)

# DRF Router (only for ViewSets)
router = DefaultRouter()
router.register(r'products', ProductView, basename='product')
router.register(r'categories', CategoryView, basename='category')
router.register(r'guest-users', GuestUserViewSet, basename='guestuser')
router.register(r'hire-items', HireItemViewSet, basename='hireitem')
router.register(r'shipping-addresses', ShippingAddressViewSet, basename='shippingaddress')

# URL Patterns
api_urlpatterns = [
    # API Base Routes from DRF router
    path('', include(router.urls)),

    # Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # User
    path('user-profile/', user_profile, name='user-profile'),

    # Orders
    path('orders/', create_order, name='create-order'),
    path('api/orders/<str:order_id>/status/', get_order_status),
    path('orders/<str:order_id>/invoice/', invoice_pdf_view, name='invoice-pdf'),

    # M-Pesa
    path('payment/mpesa/initiate/', initiate_payment, name='initiate-payment'),

    # Courier
    path('courier/', create_courier_order, name='create-courier-order'),

    # Upload url - FIXED: use the imported function directly
    path('upload-image/', upload_image, name='upload_image'),

    path('test-mongo/', test_mongo_connection, name='test-mongo'),
]


urlpatterns = [
    # Redirect root to API base
    path('', RedirectView.as_view(url='/api/', permanent=False)),

    # Custom Admin Login BEFORE default admin
    path('admin/login/', NoSignalLoginView.as_view(), name='login'),
    path('admin/', admin.site.urls),
    
    # API URLs
    path('api/', include(api_urlpatterns)),
]

