from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model
from bson import ObjectId
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

class MongoJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_id = validated_token.get("user_id")

        if not user_id:
            raise AuthenticationFailed("Token contained no identifiable user", code="no_user_id")

        try:
            if isinstance(user_id, str):
                try:
                    obj_id = ObjectId(user_id)
                except Exception:
                    obj_id = user_id  # leave as string/int
                user_id = obj_id

            return User.objects.get(id=user_id)

        except User.DoesNotExist:
            raise AuthenticationFailed("User not found", code="user_not_found")
