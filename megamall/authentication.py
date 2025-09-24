from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model
from bson import ObjectId
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

class MongoJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_id = validated_token.get("user_id")

        try:
            # Convert string to ObjectId if needed
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
            return User.objects.get(id=user_id)
        except Exception:
            raise AuthenticationFailed("User not found", code="user_not_found")
