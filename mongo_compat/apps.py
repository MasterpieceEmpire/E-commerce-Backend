from django.apps import AppConfig



class AuthConfig(AppConfig):
    name = 'django.contrib.auth'
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"

class ContentTypesConfig(AppConfig):
    name = 'django.contrib.contenttypes'
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"
