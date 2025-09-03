# megamall/auth_backends.py
from django.contrib.auth.backends import ModelBackend

class NoSignalModelBackend(ModelBackend):
    """
    Custom authentication backend that never triggers signals
    """
    def get_user(self, user_id):
        try:
            user = super().get_user(user_id)
            # Ensure we don't trigger any signals during user retrieval
            return user
        except:
            return None

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username, password, **kwargs)
        # Don't trigger any signals during authentication
        return user