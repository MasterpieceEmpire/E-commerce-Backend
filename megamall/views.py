# Standard Library
import base64
import logging
import re
import os
import json
import traceback
import ssl
import urllib.request
from datetime import datetime
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
from django.views.decorators.csrf import csrf_exempt

# Third-party packages
from pymongo import MongoClient
import certifi
import cloudinary
import cloudinary.api
import cloudinary.uploader
import requests
import sendgrid
from decouple import config
from requests.auth import HTTPBasicAuth
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
    Upload an image to Cloudinary and return the URL
    """
    try:
        image_file = request.FILES.get('image')
        folder = request.data.get('folder', 'general')
        
        if not image_file:
            return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Upload to Cloudinary
        from .utils import upload_to_cloudinary
        result = upload_to_cloudinary(image_file, folder)
        
        return Response({
            "url": result['secure_url'],
            "public_id": result['public_id'],
            "format": result['format']
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
    serializer_class = ProductSerializer

    def get_queryset(self):
        category_slug = self.request.query_params.get("category")
        queryset = Product.objects.all()

        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        return queryset.order_by('-id')

    def get_serializer_context(self):
        return {'request': self.request}


class CategoryView(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class GuestUserViewSet(viewsets.ModelViewSet):
    queryset = GuestUser.objects.all()
    serializer_class = GuestUserSerializer
    http_method_names = ["get", "post"]

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
            refresh = RefreshToken.for_user(guest_user)

            return Response(
                {**serializer.data, "token": str(refresh.access_token)}, status=201
            )

        except IntegrityError:
            return Response(
                {"detail": "Guest user with this email already exists."}, status=409
            )
        except Exception as e:
            logger.error(f"Guest registration error: {str(e)}")
            return Response({"detail": "An error occurred."}, status=500)


class ShippingAddressViewSet(viewsets.ModelViewSet):
    queryset = ShippingAddress.objects.all()
    serializer_class = ShippingAddressSerializer


class HireItemViewSet(viewsets.ModelViewSet):
    serializer_class = HireItemSerializer

    def get_queryset(self):
        return queryset.order_by('-id')

    def get_serializer_context(self):
        return {'request': self.request}



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
        
        # Process order
        with transaction.atomic():
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
                "orderId": order.id,
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
        # ✅ Ensure UUID type
        order_uuid = uuid.UUID(str(order_id))
        order = get_object_or_404(Order, id=order_uuid)

        serializer = OrderSerializer(order)
        return Response(serializer.data)

    except ValueError:
        # If order_id isn’t a valid UUID
        logger.warning(f"Invalid UUID format for order_id: {order_id}")
        return Response({"detail": "Invalid order ID format"}, status=400)

    except Exception as e:
        logger.warning(f"Order status fetch failed for {order_id}: {e}")
        return Response({"detail": f"Order not found: {str(e)}"}, status=404)


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
        data = JSONParser().parse(request)

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
                "id": courier_order.id
            }, status=201)

        return JsonResponse({
            "error": "Invalid data",
            "details": serializer.errors
        }, status=400)

    except Exception as e:
        logger.error(f"Courier order error: {str(e)}")
        traceback.print_exc()
        return JsonResponse({"error": "Failed to submit courier order."}, status=500)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def mpesa_access_token_view(request):
    consumer_key = config("MPESA_CONSUMER_KEY")
    consumer_secret = config("MPESA_CONSUMER_SECRET")
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    try:
        response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
        access_token = response.json().get("access_token")

        if access_token:
            return JsonResponse({"token": access_token}, status=200)
        else:
            return JsonResponse({"error": "Failed to retrieve token"}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def initiate_payment(request):
    phone = request.data.get("phone") or getattr(request.user, "phone", None)
    amount = request.data.get("amount")

    if not phone or not amount:
        return JsonResponse({"error": "Phone number and amount are required."}, status=400)

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"error": "Amount must be a positive number."}, status=400)

    if not re.fullmatch(r"^2547\d{8}$", str(phone)):
        return JsonResponse({"error": "Phone number must be in format 2547XXXXXXXX."}, status=400)

    # Generate Access Token
    consumer_key = config("MPESA_CONSUMER_KEY")
    consumer_secret = config("MPESA_CONSUMER_SECRET")
    token_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    token_response = requests.get(token_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    access_token = token_response.json().get("access_token")

    if not access_token:
        return JsonResponse({"error": "Failed to obtain M-Pesa access token."}, status=500)

    # Prepare STK Push Request
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    shortcode = config("MPESA_SHORTCODE")
    passkey = config("MPESA_PASSKEY")
    callback_url = config("MPESA_CALLBACK_URL")

    data_to_encode = shortcode + passkey + timestamp
    password = base64.b64encode(data_to_encode.encode()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": int(phone),
        "PartyB": shortcode,
        "PhoneNumber": int(phone),
        "CallBackURL": callback_url,
        "AccountReference": "MegaMall Ltd",
        "TransactionDesc": "MegaMall Order Payment",
    }

    response = requests.post(
        "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
        headers=headers,
        json=payload,
    )

    logger.info(f"M-Pesa STK Push Response: {response.status_code} - {response.text}")

    if response.status_code == 200:
        return JsonResponse({
            "message": "Payment request sent. Check your phone to complete the transaction.",
            "safaricom_response": response.json()
        }, status=200)
    else:
        return JsonResponse(response.json(), status=response.status_code)


@csrf_exempt
def mpesa_callback(request):
    try:
        callback_data = json.loads(request.body)
        logger.info(f"M-Pesa Callback Data: {json.dumps(callback_data)}")
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"}, status=200)
    except Exception as e:
        logger.error(f"Callback processing error: {e}")
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