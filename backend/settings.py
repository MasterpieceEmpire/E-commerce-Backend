# settings.py

import os
from pathlib import Path
from decouple import config
from django.core.management.utils import get_random_secret_key
from datetime import timedelta

# -------------------------------------------------------------------
# BASE DIR
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------
# SECURITY
# -------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY", default=get_random_secret_key())
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = ["*"]  # ⚠️ Change in production (add domain or IP)

# -------------------------------------------------------------------
# MongoDB Backend Patch (Avoid blocking server_info() call)
# -------------------------------------------------------------------
try:
    from django_mongodb_backend.base import DatabaseWrapper

    def patched_get_database_version(self):
        return (5, 0)  # Faking a supported MongoDB version

    DatabaseWrapper.get_database_version = patched_get_database_version
except Exception as e:
    print("MongoDB backend patch failed:", e)

# -------------------------------------------------------------------
# APPLICATION DEFINITION
# -------------------------------------------------------------------
INSTALLED_APPS = [
    'cloudinary',
    'cloudinary_storage',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    'corsheaders',
    "megamall.apps.MegamallConfig",
    "rest_framework_simplejwt",
]

# Use custom GuestUser model instead of Django's default User
AUTH_USER_MODEL = "megamall.GuestUser"

# -------------------------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'megamall.middleware.EarlyPatchMiddleware',
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -------------------------------------------------------------------
# ROOT & URLS
# -------------------------------------------------------------------
ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

# -------------------------------------------------------------------
# CORS & SECURITY
# -------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "https://masterpiece-frontend.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "https://masterpiece-frontend.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# -------------------------------------------------------------------
# REST FRAMEWORK
# -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=240),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,  # ⚠️ CRITICAL: Set this to False for MongoDB
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# -------------------------------------------------------------------
# DATABASE (MongoDB Atlas)
# -------------------------------------------------------------------
MONGO_URI = config("MONGO_URI")
MONGO_DB_NAME = config("MONGO_DB_NAME", default="Masterpiece")

DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "NAME": MONGO_DB_NAME,
        "CLIENT": {
            "host": MONGO_URI,
        }
    }
}

# -------------------------------------------------------------------
# SESSION SETTINGS
# -------------------------------------------------------------------
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_NAME = 'sessionid'
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# -------------------------------------------------------------------
# LANGUAGE & TIMEZONE
# -------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# STATIC & MEDIA FILES
# -------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# -------------------------------------------------------------------
# DEFAULT PRIMARY KEY FIELD
# -------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------------------
# CLOUDINARY STORAGE CONFIGURATION
# -------------------------------------------------------------------
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET'),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
