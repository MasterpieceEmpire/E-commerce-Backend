# models.py
import uuid
from cloudinary.models import CloudinaryField
from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django_mongodb_backend.fields import ObjectIdAutoField
from bson import ObjectId


class GuestUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # ✅ hash the password properly
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class GuestUser(AbstractBaseUser, PermissionsMixin):
    id = models.CharField(primary_key=True, max_length=24, default=lambda: str(ObjectId()), editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    subscribed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = GuestUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

class Category(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    # ... other fields
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # The image field will now use Cloudinary for storage due to settings.py
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    description = models.TextField()

    def __str__(self):
        return self.name


class ShippingAddress(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    DELIVERY_METHOD_CHOICES = [
        ('pickup', 'Pickup'),
        ('delivery', 'Delivery'),
    ]

    guest_user = models.ForeignKey(
        GuestUser,
        on_delete=models.SET_NULL,
        related_name='shipping_addresses',
        null=True,
        blank=True
    )

    deliveryMethod = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES, default='delivery')
    selectedStoreId = models.CharField(max_length=100, blank=True, null=True)
    collectorName = models.CharField(max_length=255, blank=True, null=True)
    collectorPhone = models.CharField(max_length=20, blank=True, null=True)

    full_name = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.full_name and self.address:
            return f"{self.full_name} - {self.address[:30]}..."
        elif self.deliveryMethod == 'pickup' and self.collectorName:
            return f"Pickup for {self.collectorName} at {self.selectedStoreId}"
        return f"Shipping Address #{self.id}"


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    guest_user = models.ForeignKey(
        GuestUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders'
    )
    shipping_address = models.ForeignKey(
        ShippingAddress, on_delete=models.SET_NULL, null=True, blank=True
    )
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, default='pending')  # pending, initiated, paid, failed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.id)

    def get_invoice_context(self):
        return {
            "order": self,
            "items": self.order_items.all(),
            "guest_user": self.guest_user,
            "shipping": self.shipping_address,
        }


class OrderItem(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name if self.product else 'Deleted Product'} x {self.quantity}"


class HireItem(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='hire_items/', blank=True, null=True)
    details = models.TextField(blank=True)
    hire_price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    hire_price_per_day = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name


class CourierOrder(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    ACTION_CHOICES = [
        ('send', 'Send'),
        ('receive', 'Receive'),
    ]

    parcel_action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    from_address = models.CharField(max_length=255, blank=True, null=True)
    to_address = models.CharField(max_length=255, blank=True, null=True)
    selected_item = models.CharField(max_length=100, blank=True, null=True)
    item_price = models.IntegerField(blank=True, null=True)
    item_type = models.CharField(max_length=100, blank=True, null=True)
    order_type = models.CharField(max_length=10, choices=ACTION_CHOICES, blank=True, null=True)

    delivery_fee = models.IntegerField(blank=True, null=True)
    total = models.IntegerField(blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)

    contact_name = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    recipient_name = models.CharField(max_length=100, blank=True, null=True)
    recipient_phone = models.CharField(max_length=20, blank=True, null=True)
    delivery_location = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.parcel_action.capitalize()} Order - {self.contact_name} ({self.created_at.date()})"