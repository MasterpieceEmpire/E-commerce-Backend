# megamall/admin.py
from django.contrib import admin
from .models import Product, Category, HireItem, GuestUser
# Register your models here.
admin.site.register(Product)
admin.site.register(Category)

admin.site.register(HireItem)
admin.site.register(GuestUser)

