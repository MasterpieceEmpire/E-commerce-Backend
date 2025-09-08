from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .models import Product, Category, GuestUser, ShippingAddress, Order, OrderItem, CourierOrder, HireItem
import cloudinary.uploader
import cloudinary

# ----------------------------
# Product Serializer
# ----------------------------
class ProductSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    category = serializers.SlugRelatedField(
        queryset=Category.objects.all(),
        slug_field='name'
    )
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'image', 'image_url', 'description', 'category']
        extra_kwargs = {
            'image': {'write_only': True}  # Hide this field on read
        }
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url)
        return None

    def create(self, validated_data):
        image_file = validated_data.pop('image', None)
        if image_file:
            try:
                upload_result = cloudinary.uploader.upload(
                    image_file,
                    folder="products",
                    unique_filename=True,
                    resource_type="image"
                )
                validated_data['image'] = upload_result.get('public_id')
                validated_data['image_url'] = upload_result.get('secure_url')
            except Exception as e:
                raise serializers.ValidationError({"image": f"Image upload failed: {str(e)}"})
        return super().create(validated_data)

    def update(self, instance, validated_data):
        image_file = validated_data.pop('image', None)
        if image_file:
            # Delete old image from Cloudinary if it exists
            if instance.image:
                cloudinary.uploader.destroy(instance.image)
            
            try:
                upload_result = cloudinary.uploader.upload(
                    image_file,
                    folder="products",
                    unique_filename=True,
                    resource_type="image"
                )
                validated_data['image'] = upload_result.get('public_id')
                validated_data['image_url'] = upload_result.get('secure_url')
            except Exception as e:
                raise serializers.ValidationError({"image": f"Image upload failed: {str(e)}"})
        return super().update(instance, validated_data)

# ----------------------------
# Category Serializer
# ----------------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

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
    product_image_url = serializers.ReadOnlyField(source='product.image.url')

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_image_url', 'quantity', 'price']
        read_only_fields = ['id']

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
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url)
        return None

    def create(self, validated_data):
        image_file = validated_data.pop('image', None)
        if image_file:
            try:
                upload_result = cloudinary.uploader.upload(
                    image_file,
                    folder="hire_items",
                    unique_filename=True,
                    resource_type="image"
                )
                validated_data['image'] = upload_result.get('public_id')
                validated_data['image_url'] = upload_result.get('secure_url')
            except Exception as e:
                raise serializers.ValidationError({"image": f"Image upload failed: {str(e)}"})
        return super().create(validated_data)

    def update(self, instance, validated_data):
        image_file = validated_data.pop('image', None)
        if image_file:
            if instance.image:
                cloudinary.uploader.destroy(instance.image)
            
            try:
                upload_result = cloudinary.uploader.upload(
                    image_file,
                    folder="hire_items",
                    unique_filename=True,
                    resource_type="image"
                )
                validated_data['image'] = upload_result.get('public_id')
                validated_data['image_url'] = upload_result.get('secure_url')
            except Exception as e:
                raise serializers.ValidationError({"image": f"Image upload failed: {str(e)}"})
        return super().update(instance, validated_data)

# ----------------------------
# Courier Order Serializer
# ----------------------------
class CourierOrderSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True) # Use CharField for string representation of ObjectId
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