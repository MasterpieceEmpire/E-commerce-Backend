# Standard Library
import uuid
import base64
import logging
import re
import os
import json
import traceback
import ssl
import urllib.request
from datetime import datetime, timedelta
from io import BytesIO

# Django Core
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpResponse
from django.db import connection
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import get_template
from django.urls import reverse
from django.utils.html import strip_tags
from rest_framework.parsers import MultiPartParser, FormParser
from bson import ObjectId
from django.http import Http404
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt

# Third-party packages
from k2connect import k2connect
from pymongo import MongoClient
import certifi
import cloudinary
import cloudinary.api
import cloudinary.uploader
import requests
import sendgrid
from decouple import config
from requests.auth import HTTPBasicAuth
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from sendgrid.helpers.mail import (
    Mail,
    Email,
    To,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition,
)
from xhtml2pdf import pisa

# Project-local imports
from megamall.models import (
    Product,
    Category,
    GuestUser,
    ShippingAddress,
    Order,
    OrderItem,
    HireItem,
    CourierOrder,
)
from megamall.serializers import (
    ProductSerializer,
    CategorySerializer,
    GuestUserSerializer,
    ShippingAddressSerializer,
    CustomTokenObtainPairSerializer,
    OrderSerializer,
    HireItemSerializer,
    CourierOrderSerializer,
)
CLIENT_ID = os.getenv("KOPOKOPO_CLIENT_ID")
CLIENT_SECRET = os.getenv("KOPOKOPO_CLIENT_SECRET")
BASE_URL = os.getenv("KOPOKOPO_BASE_URL", "https://api.kopokopo.com")  # sandbox/live
TILL_NUMBER = os.getenv("KOPOKOPO_TILL_NUMBER")
CALLBACK_URL = os.getenv("KOPOKOPO_CALLBACK_URL")



ssl_context = ssl.create_default_context(cafile=certifi.where())
urllib.request.install_opener(
    urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))
)

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def test_mongo_connection(request):
    """Test MongoDB connection directly with pymongo"""
    try:
        MONGO_URI = config("MONGO_URI")
        MONGO_DB_NAME = config("MONGO_DB_NAME", default="Masterpiece")
        
        # Debug output to see what URI is being used
        print(f"Attempting to connect to: {MONGO_URI}")
        
        # Test connection directly
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            socketTimeoutMS=10000,
            connectTimeoutMS=10000
        )
        
        # Test the connection
        client.admin.command('ping')
        
        # Get database info
        db = client[MONGO_DB_NAME]
        collections = db.list_collection_names()
        
        return Response({
            "status": "success",
            "message": "MongoDB connection successful",
            "database": MONGO_DB_NAME,
            "collections": collections,
            "collections_count": len(collections)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"MongoDB connection failed: {str(e)}")
        return Response({
            "status": "error",
            "message": f"MongoDB connection failed: {str(e)}",
            "uri_used": MONGO_URI if 'MONGO_URI' in locals() else "Not found"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_image(request):
    """
    Upload an image to Cloudinary and return the URL in the correct format
    """
    try:
        image_file = request.FILES.get('image')
        folder = request.data.get('folder', 'general')
        
        if not image_file:
            return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Upload to Cloudinary with specific settings to match your URL format
        result = cloudinary.uploader.upload(
            image_file,
            folder=folder,
            use_filename=True,  # This helps maintain original filename structure
            unique_filename=True,  # This ensures unique names like thufhhtaxymd5v1fzyan
            overwrite=False,
            resource_type="auto"  # Automatically detect image type
        )
        
        # Return the URL in the exact format you want
        return Response({
            "url": result['secure_url'],  # This should match your desired format
            "public_id": result['public_id'],
            "format": result['format'],
            "version": result['version']
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Image upload error: {str(e)}")
        return Response({"error": "Failed to upload image"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
def cloudinary_debug(request):
    from cloudinary_storage.storage import MediaCloudinaryStorage
    storage = MediaCloudinaryStorage()
    
    return JsonResponse({
        'cloudinary_configured': hasattr(settings, 'CLOUDINARY_STORAGE'),
        'default_storage': settings.DEFAULT_FILE_STORAGE,
        'storage_class': str(storage.__class__),
        'can_access_cloudinary': True  # This will error if Cloudinary isn't configured
    })

class NoSignalLoginView(LoginView):
    """
    Custom admin login view that skips updating last_login
    (important for MongoDB where signals can break).
    """
    template_name = "admin/login.html"  # ✅ use the admin login template

    def form_valid(self, form):
        user = form.get_user()
        # Log the user in WITHOUT triggering the last_login update
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect("/admin/")  # ✅ force redirect to admin dashboard



class ProductView(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = ProductSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # keep only multipart/form parsers

    def get_queryset(self):
        category_slug = self.request.query_params.get("category")
        queryset = Product.objects.all()
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset.order_by('-id')

    def get_serializer_context(self):
        return {'request': self.request}

    def create(self, request, *args, **kwargs):
        """
        Let DRF parse multipart/form-data and give us request.data (includes files).
        Avoid manual merging of POST and FILES — that produced tricky edge cases.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class CategoryView(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class GuestUserViewSet(viewsets.ModelViewSet):
    queryset = GuestUser.objects.all()
    serializer_class = GuestUserSerializer
    http_method_names = ["get", "post"]

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]  # open signup
        return [IsAuthenticatedOrReadOnly()]  # restrict listing to authenticated

    def create(self, request, *args, **kwargs):
        data = request.data
        email, password = data.get("email"), data.get("password")
        if not email or not password:
            return Response({"detail": "Email and password are required."}, status=400)

        try:
            guest_user = GuestUser.objects.create(
                email=email,
                password=make_password(password),
                subscribed=data.get("subscribed", True),
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                phone=data.get("phone", ""),
            )
            serializer = self.get_serializer(guest_user)

            # create refresh + access tokens
            refresh = RefreshToken.for_user(guest_user)
            access = str(refresh.access_token)

            return Response(
                {
                    **serializer.data,
                    "access": access,
                    "refresh": str(refresh)
                },
                status=201
            )

        except IntegrityError:
            return Response(
                {"detail": "Guest user with this email already exists."}, status=409
            )
        except Exception as e:
            logger.error(f"Guest registration error: {str(e)}")
            return Response({"detail": "An error occurred."}, status=500)


class ShippingAddressViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = ShippingAddress.objects.all()
    serializer_class = ShippingAddressSerializer


class HireItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = HireItemSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # keep only multipart/form parsers

    def get_queryset(self):
        return HireItem.objects.all().order_by('-id')

    def get_serializer_context(self):
        return {'request': self.request}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    try:
        serializer = GuestUserSerializer(request.user)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"User profile error: {e}")
        return Response({"detail": "Failed to retrieve profile."}, status=500)


def generate_invoice_pdf_in_memory(order):
    template = get_template("invoice_template.html")
    context = {
        "order": order,
        "order_items": order.order_items.all(),
        "guest_user": order.guest_user,
        "shipping_address": order.shipping_address,
    }
    html = template.render(context)
    result = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=result)
    if pisa_status.err:
        print("Error rendering PDF:", pisa_status.err)
        print(html)
        return None
    return result.getvalue()

def send_invoice_email_in_memory(user_email, invoice_context, pdf_bytes):
    subject = f"Invoice #{invoice_context['invoice_number']} - MegaMall"
    html_content = f"""
        <h2>Thank you for your order</h2>
        <p>Invoice number: {invoice_context['invoice_number']}</p>
        <p>See attached invoice PDF.</p>
    """

    encoded_file = base64.b64encode(pdf_bytes).decode()
    attachment = Attachment(
        FileContent(encoded_file),
        FileName(f"invoice_{invoice_context['invoice_number']}.pdf"),
        FileType("application/pdf"),
        Disposition("attachment"),
    )

    message = Mail(
        from_email=Email("masterpiecempireorders@gmail.com"),
        to_emails=[user_email, "masterpiecempireorders@gmail.com"],
        subject=subject,
        html_content=html_content,
    )
    message.attachment = attachment

    os.environ["SSL_CERT_FILE"] = certifi.where()
    sg = sendgrid.SendGridAPIClient(api_key=config("SENDGRID_API_KEY"))
    sg.send(message)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    try:
        data = request.data
        
        # Validate required data
        required_fields = ["shippingAddress", "cartItems", "totalPrice"]
        if not all(field in data for field in required_fields):
            return Response(
                {"detail": "Missing required fields"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # REMOVE transaction.atomic() - MongoDB doesn't support Django transactions
        shipping_serializer = ShippingAddressSerializer(data=data["shippingAddress"])
        if not shipping_serializer.is_valid():
            return Response(
                {"detail": "Invalid shipping address", "errors": shipping_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        shipping_address = shipping_serializer.save()
        
        order = Order.objects.create(
            guest_user=request.user,
            shipping_address=shipping_address,
            total_price=data["totalPrice"],
            status="pending"
        )
        
        # Add order items
        for item in data["cartItems"]:
            product = get_object_or_404(Product, id=item.get("id"))
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item.get("quantity", 1),
                price=product.price
            )
            
        return Response({
            "orderId": str(order.id),  # Convert ObjectId to string
            "message": "Order created successfully"
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Order creation failed: {str(e)}")
        return Response(
            {"detail": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_order_status(request, order_id):
    try:
        # Handle both ObjectId and string representations
        try:
            # First try as ObjectId
            order_obj_id = ObjectId(order_id)
            order = Order.objects.get(id=order_obj_id)
        except:
            # If that fails, try as string
            order = Order.objects.get(id=order_id)

        serializer = OrderSerializer(order)
        return Response(serializer.data)

    except Order.DoesNotExist:
        logger.warning(f"Order not found: {order_id}")
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Order status fetch failed for {order_id}: {str(e)}")
        return Response({"detail": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    response = HttpResponse(content_type="application/pdf")
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("We had some errors <pre>" + html + "</pre>")
    return response


def invoice_pdf_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    context = {
        "invoice_number": order.id,
        "items": order.order_items.all(),
        "subtotal": order.total_price,
        "shipping": 0,
        "tax": 0,
        "grand_total": order.total_price,
        "shipping_address": order.shipping_address,
    }
    return render_to_pdf("invoice_template.html", context)


from rest_framework.parsers import JSONParser
from rest_framework import status
from megamall.serializers import CourierOrderSerializer

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def create_courier_order(request):
    try:
        # Use request.data instead of JSONParser for better form handling
        data = request.data

        # Remove any fields not part of the model
        cleaned_data = data.copy()
        cleaned_data.pop("item_type", None)
        cleaned_data.pop("order_type", None)

        serializer = CourierOrderSerializer(data=cleaned_data)
        if serializer.is_valid():
            courier_order = serializer.save()

            # Build HTML email content
            subject = "New Courier Order - Masterpiece Empire"
            html_content = f"""
                <h2>New Courier Order Submitted</h2>
                <p><strong>Action:</strong> {courier_order.parcel_action}</p>
                <p><strong>Name:</strong> {courier_order.contact_name}</p>
                <p><strong>Phone:</strong> {courier_order.contact_phone}</p>
                <p><strong>From:</strong> {courier_order.from_address}</p>
                <p><strong>To:</strong> {courier_order.to_address}</p>
                <p><strong>Selected Item:</strong> {courier_order.selected_item}</p>
                <p><strong>Total:</strong> KES {courier_order.total}</p>
                <p><strong>Payment Method:</strong> {courier_order.payment_method}</p>
                <p><strong>Notes:</strong> {courier_order.notes}</p>
                <p><strong>Time:</strong> {courier_order.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
            """

            # Send email using SendGrid
            sg = sendgrid.SendGridAPIClient(api_key=config("SENDGRID_API_KEY"))
            message = Mail(
                from_email=Email("masterpiecempireorders@gmail.com"),
                to_emails=["masterpiecempireorders@gmail.com"],
                subject=subject,
                html_content=html_content,
            )
            sg.send(message)

            return JsonResponse({
                "message": "Courier order submitted and email sent.",
                "id": str(courier_order.id)  # Convert ObjectId to string
            }, status=201)

        return JsonResponse({
            "error": "Invalid data",
            "details": serializer.errors
        }, status=400)

    except Exception as e:
        logger.error(f"Courier order error: {str(e)}")
        traceback.print_exc()
        return JsonResponse({"error": "Failed to submit courier order."}, status=500)

# Switch between sandbox and live using env var KOPOKOPO_ENV ("sandbox" or "live")
# Switch between sandbox and live using env var KOPOKOPO_ENV ("sandbox" or "live")
ENVIRONMENT = config("KOPOKOPO_ENV", default="sandbox")

# For direct API calls (no trailing slash)
KOPOKOPO_BASE_URL = (
    "https://sandbox.kopokopo.com" if ENVIRONMENT == "sandbox" else "https://api.kopokopo.com"
)

# For SDK (with trailing slash) - if you decide to use it later
KOPOKOPO_BASE_URL_SDK = (
    "https://sandbox.kopokopo.com" if ENVIRONMENT == "sandbox" else "https://api.kopokopo.com"
)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def debug_kopokopo_config(request):
    return JsonResponse({
        "base_url": KOPOKOPO_BASE_URL,
        "client_id": CLIENT_ID[:8] + "..." if CLIENT_ID else "NOT_SET",
        "till_number": TILL_NUMBER,
        "callback_url": CALLBACK_URL,
        "environment": ENVIRONMENT
    })

# 🔹 Get OAuth Access Token
kopokopo_token_cache = {"token": None, "expires_at": None}

def get_kopokopo_access_token():
    global kopokopo_token_cache

    # If cached and not expired, reuse
    if (
        kopokopo_token_cache["token"]
        and kopokopo_token_cache["expires_at"]
        and kopokopo_token_cache["expires_at"] > datetime.utcnow()
    ):
        return kopokopo_token_cache["token"]

    # ✅ Use the base URL WITHOUT trailing slash for direct API calls
    url = f"{KOPOKOPO_BASE_URL}/oauth/token"
    client_id = CLIENT_ID
    client_secret = CLIENT_SECRET

    auth_str = f"{client_id}:{client_secret}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {"grant_type": "client_credentials"}

    try:
        logger.info(f"Requesting KopoKopo token from: {url}")
        response = requests.post(url, data=payload, headers=headers)
        logger.info(f"KopoKopo token response: {response.status_code} - {response.text}")
        response.raise_for_status()

        data = response.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)

        # Cache token with expiry
        kopokopo_token_cache["token"] = token
        kopokopo_token_cache["expires_at"] = datetime.utcnow() + timedelta(seconds=expires_in - 60)

        return token
    except Exception as e:
        logger.error(f"KopoKopo token error: {e}")
        return None
    
def normalize_phone(phone: str) -> str:
    """
    Ensure phone numbers are in +2547XXXXXXXX format
    """
    phone = str(phone).strip()
    if phone.startswith("254"):
        phone = "+" + phone
    elif phone.startswith("0"):
        phone = "+254" + phone[1:]
    elif not phone.startswith("+254"):
        phone = "+254" + phone
    return phone

# Initialize SDK
k2connect.initialize(CLIENT_ID, CLIENT_SECRET, BASE_URL)

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def initiate_payment(request):
    try:
        phone = normalize_phone(request.data.get("phone"))

        raw_amount = request.data.get("amount")
        if raw_amount is None:
            return JsonResponse({"error": "Amount is required"}, status=400)

        import re
        clean_amount_str = re.sub(r"[^\d.]", "", str(raw_amount))
        try:
            amount = str(int(float(clean_amount_str)))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid amount"}, status=400)

        first_name = request.data.get("first_name", "Customer")
        last_name = request.data.get("last_name", "")
        order_id = request.data.get("order_id", "order")

        if not phone:
            return JsonResponse({"error": "Phone is required"}, status=400)

        token_service = k2connect.Tokens
        token_resp = token_service.request_access_token()
        access_token = token_service.get_access_token(token_resp)

        if not access_token:
            return JsonResponse({"error": "Failed to fetch access token"}, status=500)

        receive_payments_service = k2connect.ReceivePayments
        request_payload = {
            "access_token": access_token,
            "callback_url": CALLBACK_URL,
            "first_name": first_name,
            "last_name": last_name,
            "email": "masterpieceempie@gmail.com",
            "payment_channel": "MPESA",
            "phone_number": phone,
            "till_number": "K107940",
            "amount": amount,  
            "currency": "KES",
            "metadata": {
                "customer_id": str(request.user.id),
                "order_id": order_id,
                "notes": f"Payment for order {order_id}"
            }
        }

        payment_location_url = receive_payments_service.create_payment_request(request_payload)
        logger.info(f"Payment request URL: {payment_location_url}")

        return JsonResponse({
            "status": "initiated",
            "message": "Payment request sent. Check your phone to complete the transaction.",
            "location": payment_location_url
        })

    except Exception as e:
        logger.exception("Unexpected error in initiate_payment")
        return JsonResponse({"error": str(e)}, status=500)

    
    
# 🔹 Handle Payment Callback
@csrf_exempt
def kopokopo_callback(request):
    try:
        # KopoKopo sends POST requests with JSON payload
        if request.method == 'POST':
            callback_data = json.loads(request.body.decode('utf-8'))
            logger.info(f"KopoKopo Callback Received: {callback_data}")
            
            # Process the callback data
            # Typically contains: event_type, resource_id, status, etc.
            
            return JsonResponse({"status": "success"}, status=200)
        else:
            return JsonResponse({"error": "Method not allowed"}, status=405)
            
    except Exception as e:
        logger.error(f"KopoKopo callback error: {e}")
        return JsonResponse({"error": "Invalid callback"}, status=400)


from django.contrib.auth import get_user_model

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def create_superuser_view(request):
    User = get_user_model()
    email = "admin@example.com"
    password = "admin123"

    if User.objects.filter(email=email).exists():
        return JsonResponse({"status": "exists", "message": "Superuser already exists"})

    try:
        superuser = User.objects.create_superuser(email=email, password=password)
        return JsonResponse({"status": "created", "message": "Superuser created successfully"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)