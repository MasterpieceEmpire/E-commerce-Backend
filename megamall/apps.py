# megamall/apps.py

from django.apps import AppConfig
from django.db.models.fields import AutoField
from django_mongodb_backend.fields import ObjectIdAutoField

class MegamallConfig(AppConfig):
    default_auto_field = 'django_mongodb_backend.fields.ObjectIdAutoField'
    name = 'megamall'

    def ready(self):
        """
        Apply all MongoDB compatibility patches
        """
        # Apply patches in the correct order
        self.patch_last_login_signal()
        self.patch_user_save_method()
        self.patch_core_models()
        self.add_admin_compatibility()

    def patch_last_login_signal(self):
        """
        Completely disable the last_login signal to prevent MongoDB errors
        """
        try:
            # Import required modules
            import django.dispatch
            from django.contrib.auth import user_logged_in
            
            # Create a completely new signal object
            new_signal = django.dispatch.Signal()
            
            # Replace the signal in the auth module
            import django.contrib.auth
            django.contrib.auth.user_logged_in = new_signal
            
            # Clear any existing receivers
            new_signal.receivers = []
            new_signal.sender_receivers_cache = {}
            
            print("Successfully disabled last_login signal")
            
        except Exception as e:
            print(f"Failed to patch last_login signal: {e}")

    def patch_user_save_method(self):
        """
        Patch the User model's save method to ignore last_login updates
        """
        try:
            from django.contrib.auth.models import User
            
            # Store the original save method
            original_save = User.save
            
            def mongodb_save(self, *args, **kwargs):
                # Check if this is a last_login-only update
                update_fields = kwargs.get('update_fields')
                
                if update_fields and set(update_fields) == {'last_login'}:
                    # Skip the save operation for last_login updates
                    # The value is already set on the instance
                    return
                
                # For all other operations, use the original save method
                return original_save(self, *args, **kwargs)
            
            # Replace the save method
            User.save = mongodb_save
            print("Successfully patched User save method")
            
        except Exception as e:
            print(f"Failed to patch User save method: {e}")

    def patch_core_models(self):
        """
        Patch core Django models to use MongoDB ObjectId fields
        """
        try:
            from django.contrib.contenttypes.models import ContentType
            from django.contrib.auth.models import Group, Permission, User
            from django.contrib.admin.models import LogEntry

            models_to_patch = [ContentType, LogEntry, Group, Permission, User]
            
            for model in models_to_patch:
                for field in model._meta.get_fields():
                    if isinstance(field, AutoField):
                        field.__class__ = ObjectIdAutoField
                        field.primary_key = True
                        break
            
            print("Successfully patched core models for MongoDB")
            
        except Exception as e:
            print(f"Failed to patch core models: {e}")

    def add_admin_compatibility(self):
        """
        Add admin compatibility methods to User model
        """
        try:
            from django.contrib.auth.models import User
            
            if not hasattr(User, "full_name"):
                def full_name(self):
                    return f"{self.first_name} {self.last_name}".strip()
                
                User.add_to_class("full_name", full_name)
                print("Successfully added full_name method to User model")
                
        except Exception as e:
            print(f"Failed to add admin compatibility: {e}")