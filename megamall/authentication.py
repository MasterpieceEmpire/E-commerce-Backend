from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model

User = get_user_model()

class MongoJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_id = validated_token.get("user_id")
        if not user_id:
            raise AuthenticationFailed("Token contained no identifiable user", code="no_user_id")
        try:
            return User.objects.get(id=str(user_id))  # always string
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found", code="user_not_found")
