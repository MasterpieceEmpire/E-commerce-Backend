# megamall/serializers.py
from io import BytesIO
from bson import ObjectId
from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .models import Product, Category, GuestUser, ShippingAddress, Order, OrderItem, CourierOrder, HireItem
import cloudinary.uploader
from .fields import ObjectIdField
from cloudinary.utils import cloudinary_url

# ----------------------------
# Base Serializer with ObjectId handling
# ----------------------------
class BaseMongoDBSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        for key, value in rep.items():
            if isinstance(value, ObjectId):
                rep[key] = str(value)
        return rep

# ----------------------------
# Base serializer with Cloudinary
# ----------------------------
# megamall/serializers.py

class BaseMongoDBSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        for key, value in rep.items():
            if isinstance(value, ObjectId):
                rep[key] = str(value)
        return rep

# ----------------------------
# SIMPLIFIED Base serializer - Just accepts image_url as string
# ----------------------------
class BaseCloudinarySerializer(BaseMongoDBSerializer):
    # Remove the complex image handling since we upload separately
    image_url = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        abstract = True

    # Remove the create and update methods that reference upload_to_cloudinary
    # Let ModelSerializer handle normal field saving

    def create(self, validated_data):
        # Simply create the instance with the provided data
        # image_url will be saved as a string from the frontend
        ModelClass = self.Meta.model
        instance = ModelClass.objects.create(**validated_data)
        return instance

    def update(self, instance, validated_data):
        # Simply update the instance with the provided data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

# ----------------------------
# Product Serializer
# ----------------------------
class ProductSerializer(BaseCloudinarySerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta(BaseCloudinarySerializer.Meta):
        model = Product
        fields = ['id', 'name', 'price', 'description', 'category', 'category_name', 'image_url']

# ----------------------------
# HireItem Serializer
# ----------------------------
class HireItemSerializer(BaseCloudinarySerializer):
    class Meta(BaseCloudinarySerializer.Meta):
        model = HireItem
        fields = ['id', 'name', 'hire_price_per_day', 'hire_price_per_hour', 'image_url', 'details']


# ----------------------------
# Category Serializer
# ----------------------------
class CategorySerializer(BaseMongoDBSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

# ----------------------------
# GuestUser Serializer
# ----------------------------
class GuestUserSerializer(BaseMongoDBSerializer):
    class Meta:
        model = GuestUser
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'subscribed']

# ----------------------------
# Shipping Address Serializer
# ----------------------------
class ShippingAddressSerializer(BaseMongoDBSerializer):
    guest_user = serializers.CharField(required=False)

    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'guest_user', 'deliveryMethod', 'selectedStoreId',
            'collectorName', 'collectorPhone', 'full_name', 'address',
            'city', 'postal_code', 'country', 'created_at'
        ]
        read_only_fields = ['created_at']

    def create(self, validated_data):
        if 'guest_user' not in validated_data and hasattr(self.context.get('request'), 'user'):
            validated_data['guest_user'] = str(self.context['request'].user.id)
        return super().create(validated_data)

# ----------------------------
# Token Serializer
# ----------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Force user_id to be your actual pk as string
        token['user_id'] = str(user.pk)
        token['email'] = user.email

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # also include user_id in the response body for convenience
        data['user_id'] = str(self.user.pk)
        data['email'] = self.user.email
        return data
    
# ----------------------------
# Order Item Serializer
# ----------------------------
class OrderItemSerializer(BaseMongoDBSerializer):
    id = serializers.CharField(read_only=True)
    product = serializers.StringRelatedField()
    product_image_url = serializers.ReadOnlyField(source='product.image_url')

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_image_url', 'quantity', 'price']

# ----------------------------
# Order Serializer
# ----------------------------
class OrderSerializer(BaseMongoDBSerializer):
    id = serializers.CharField(read_only=True)
    guest_user = GuestUserSerializer(read_only=True)
    shipping_address = ShippingAddressSerializer(read_only=True)
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'guest_user', 'shipping_address', 'payment_method',
            'total_price', 'status', 'created_at', 'order_items'
        ]

# ----------------------------
# Courier Order Serializer
# ----------------------------
class CourierOrderSerializer(BaseMongoDBSerializer):
    id = serializers.CharField(read_only=True)
    parcel_action = serializers.ChoiceField(
        choices=[("send", "send"), ("receive", "receive")],
        required=False,
        allow_blank=True
    )
    selected_item = serializers.CharField(required=False, allow_blank=True)
    item_type = serializers.CharField(required=False, allow_blank=True)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    item_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    class Meta:
        model = CourierOrder
        fields = '__all__'

    def validate(self, data):
        if 'parcel_action' in data:
            data['order_type'] = data['parcel_action']
        return data
    
class CustomRegisterSerializer(RegisterSerializer):
    username = None  # removes username completely
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def get_cleaned_data(self):
        return {
            'email': self.validated_data.get('email', ''),
            'password1': self.validated_data.get('password1', ''),
            'password2': self.validated_data.get('password2', ''),
            'first_name': self.validated_data.get('first_name', ''),
            'last_name': self.validated_data.get('last_name', ''),
            'phone': self.validated_data.get('phone', ''),
        }

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        user.phone = self.cleaned_data.get('phone')
        user.save()
        return user
