from bson import ObjectId
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .models import Product, Category, GuestUser, ShippingAddress, Order, OrderItem, CourierOrder, HireItem
import cloudinary.uploader
from .utils import upload_to_cloudinary
from cloudinary.utils import cloudinary_url


# ----------------------------
# Product Serializer
# ----------------------------
class ObjectIdField(serializers.Field):
    """Custom field to handle MongoDB ObjectId serialization"""
    def to_representation(self, value):
        return str(value) if isinstance(value, ObjectId) else value

    def to_internal_value(self, data):
        return ObjectId(data)


class BaseCloudinarySerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    image = serializers.ImageField(write_only=True, required=False)  # file input
    image_url = serializers.CharField(read_only=True)  # direct Cloudinary URL stored in DB

    class Meta:
        abstract = True
        fields = '__all__'

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if isinstance(instance.id, ObjectId):
            rep['id'] = str(instance.id)
        return rep

    def create(self, validated_data):
        image = validated_data.pop("image", None)
        instance = self.Meta.model.objects.create(**validated_data)

        if image:
            folder = getattr(self.Meta, "cloudinary_folder", "uploads")
            result = upload_to_cloudinary(image, folder=folder)
            # ✅ store secure_url directly
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
            # ✅ replace with new secure_url
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
    id = ObjectIdField(read_only=True)

    class Meta:
        model = GuestUser
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'subscribed']


# ----------------------------
# Shipping Address Serializer
# ----------------------------
class ShippingAddressSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)

    class Meta:
        model = ShippingAddress
        fields = ['all']


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
    id = ObjectIdField(read_only=True)
    product = serializers.StringRelatedField()
    product_image_url = serializers.ReadOnlyField(source='product.image.url')

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_image_url', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    guest_user = ObjectIdField(read_only=True)
    shipping_address = ShippingAddressSerializer(read_only=True)
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'guest_user', 'shipping_address',
            'payment_method', 'total_price', 'status',
            'created_at', 'order_items'
        ]

        
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
