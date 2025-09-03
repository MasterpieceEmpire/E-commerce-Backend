# megamall/backends.py
from django.contrib.auth.backends import BaseBackend
from .models import GuestUser

class MongoEngineBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        try:
            user = GuestUser.objects.get(email=username)
            if user.check_password(password):
                return user
        except GuestUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return GuestUser.objects.get(pk=user_id)
        except GuestUser.DoesNotExist:
            return None