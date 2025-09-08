from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .models import Product, Category, GuestUser, ShippingAddress, Order, OrderItem, CourierOrder, HireItem
import cloudinary.uploader
import cloudinary
import os
from django.conf import settings

# ----------------------------
# Product Serializer
# ----------------------------
class ProductSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'image', 'image_url', 'description', 'category']
    
    def get_image_url(self, obj):
        if obj.image:
            # Simple Cloudinary URL construction
            cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
            
            if isinstance(obj.image, str):
                public_id = obj.image
            else:
                public_id = obj.image.name
            
            # Remove file extension for Cloudinary public_id
            public_id = os.path.splitext(public_id)[0]
            
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}"
        return None

# ----------------------------
# Category Serializer
# ----------------------------
class CategorySerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

# ----------------------------
# GuestUser Serializer
# ----------------------------
User = get_user_model()

class GuestUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestUser
        fields = ["id", "email", "phone", "subscribed", "is_active"]

# ----------------------------
# Shipping Address Serializer
# ----------------------------
class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = '__all__'

# ----------------------------
# Token Serializer
# ----------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user_id'] = str(self.user.id)
        data['email'] = self.user.email
        return data

# ----------------------------
# Order Item Serializer
# ----------------------------
class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField()
    product_image_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_image_url', 'quantity', 'price']
        read_only_fields = ['id']

    def get_product_image_url(self, obj):
        if obj.product and obj.product.image:
            # Use the same logic as ProductSerializer
            cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
            
            if isinstance(obj.product.image, str):
                public_id = obj.product.image
            else:
                public_id = obj.product.image.name
            
            public_id = os.path.splitext(public_id)[0]
            
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}"
        return None

# ----------------------------
# Order Serializer
# ----------------------------
class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'shipping_address', 'guest_user', 'payment_method', 'total_price', 'status', 'created_at', 'order_items']
        read_only_fields = ['id']

# ----------------------------
# HireItem Serializer
# ----------------------------
class HireItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = HireItem
        fields = ['id', 'name', 'hire_price_per_day', 'hire_price_per_hour', 'image', 'image_url', 'details']
        extra_kwargs = {
            'image': {'write_only': True}
        }

    def get_image_url(self, obj):
        if obj.image:
            # Use the same logic as ProductSerializer
            cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
            
            if isinstance(obj.image, str):
                public_id = obj.image
            else:
                public_id = obj.image.name
            
            public_id = os.path.splitext(public_id)[0]
            
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}"
        return None

# ----------------------------
# Courier Order Serializer
# ----------------------------
class CourierOrderSerializer(serializers.ModelSerializer):
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