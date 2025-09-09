# megamall/serializers.py
from bson import ObjectId
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .models import Product, Category, GuestUser, ShippingAddress, Order, OrderItem, CourierOrder, HireItem
import cloudinary.uploader
from .utils import upload_to_cloudinary
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
class BaseCloudinarySerializer(BaseMongoDBSerializer):
    image = serializers.ImageField(write_only=True, required=False)
    image_url = serializers.CharField(read_only=True)

    class Meta:
        abstract = True

    def create(self, validated_data):
        image = validated_data.pop("image", None)
        ModelClass = self.Meta.model

        instance = ModelClass.objects.create(**validated_data)

        if image:
            # Normalize BEFORE calling uploader
            clean_image = normalize_uploaded_file(image)
            result = upload_to_cloudinary(clean_image, folder=getattr(self.Meta, "cloudinary_folder", "uploads"))
            instance.image_url = result.get("secure_url", "")
            instance.save()

        return instance

    def update(self, instance, validated_data):
        image = validated_data.pop("image", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if image:
            clean_image = normalize_uploaded_file(image)
            result = upload_to_cloudinary(clean_image, folder=getattr(self.Meta, "cloudinary_folder", "uploads"))
            instance.image_url = result.get("secure_url", "")

        instance.save()
        return instance


# ----------------------------
# Product Serializer
# ----------------------------
class ProductSerializer(BaseCloudinarySerializer):
    class Meta(BaseCloudinarySerializer.Meta):
        model = Product
        cloudinary_folder = "products"
        fields = "__all__"

# ----------------------------
# HireItem Serializer
# ----------------------------
class HireItemSerializer(BaseCloudinarySerializer):
    class Meta(BaseCloudinarySerializer.Meta):
        model = HireItem
        cloudinary_folder = "hire_items"
        fields = "__all__"

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
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user_id'] = str(self.user.id)
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
