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
    id = ObjectIdField(read_only=True)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Ensure all ObjectId fields are converted to strings
        for field_name, field_value in representation.items():
            if isinstance(field_value, ObjectId):
                representation[field_name] = str(field_value)
        return representation

# ----------------------------
# Product Serializer
# ----------------------------
class BaseCloudinarySerializer(BaseMongoDBSerializer):
    image = serializers.ImageField(write_only=True, required=False)
    image_url = serializers.CharField(read_only=True)

    class Meta:
        abstract = True
        fields = '__all__'

    def create(self, validated_data):
        image = validated_data.pop("image", None)
        instance = self.Meta.model.objects.create(**validated_data)

        if image:
            folder = getattr(self.Meta, "cloudinary_folder", "uploads")
            result = upload_to_cloudinary(image, folder=folder)
            instance.image_url = result["secure_url"]
            instance.save()

        return instance

    def update(self, instance, validated_data):
        image = validated_data.pop("image", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if image:
            folder = getattr(self.Meta, "cloudinary_folder", "uploads")
            result = upload_to_cloudinary(image, folder=folder)
            instance.image_url = result["secure_url"]

        instance.save()
        return instance

class ProductSerializer(BaseCloudinarySerializer):
    class Meta(BaseCloudinarySerializer.Meta):
        model = Product
        cloudinary_folder = "products"
        fields = '__all__'

class HireItemSerializer(BaseCloudinarySerializer):
    class Meta(BaseCloudinarySerializer.Meta):
        model = HireItem
        cloudinary_folder = "hire_items"
        fields = '__all__'

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
# megamall/serializers.py
class ShippingAddressSerializer(BaseMongoDBSerializer):
    guest_user = ObjectIdField(required=False)

    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'guest_user', 'deliveryMethod', 'selectedStoreId',
            'collectorName', 'collectorPhone', 'full_name', 'address',
            'city', 'postal_code', 'country', 'created_at'
        ]
        read_only_fields = ['created_at']

    def create(self, validated_data):
        # Auto-set guest_user from request if not provided
        if 'guest_user' not in validated_data and hasattr(self.context.get('request'), 'user'):
            validated_data['guest_user'] = self.context['request'].user
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
    product = serializers.StringRelatedField()
    product_image_url = serializers.ReadOnlyField(source='product.image_url')

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_image_url', 'quantity', 'price']

# ----------------------------
# Order Serializer
# ----------------------------
class OrderSerializer(BaseMongoDBSerializer):
    guest_user = ObjectIdField(read_only=True)
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