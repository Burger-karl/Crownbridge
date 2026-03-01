"""
Django settings for crownbridge_project project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env(key, default=None):
    return os.getenv(key, default)


# ------------------------------------------------------------------
# SECURITY
# ------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", "django-insecure-change-me-in-production")

# Never run DEBUG=True in production.  Set DEBUG=False in your .env
DEBUG = env("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = env(
    "localhost,127.0.0.1",
    "crown-mqge.onrender.com",
    "crownbridgeltd.com"
).split(",")

# CSRF trusted origins (required for modern Django behind a proxy)
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if not h.startswith("127") and h != "localhost"
]

# Production security headers (only active when DEBUG=False)
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000          # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# ------------------------------------------------------------------
# Application definition
# ------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'users',
    'dashboard',
    'investment',
    'payment',
    'kyc',
    'supportchat',
    'notifications',

    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',

    'cloudinary',
    'cloudinary_storage',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

ROOT_URLCONF = 'crownbridge_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.notifications_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'crownbridge_project.wsgi.application'


# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env("DB_NAME"),
        'USER': env("DB_USER"),
        'PASSWORD': env("DB_PASSWORD"),
        'HOST': env("DB_HOST"),
        'PORT': env("DB_PORT", "5432"),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}


# ------------------------------------------------------------------
# Password validation
# ------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ------------------------------------------------------------------
# Internationalisation
# ------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------------
# Static / Media files
# ------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": env("CLOUDINARY_API_KEY"),
    "API_SECRET": env("CLOUDINARY_API_SECRET"),
}
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.CustomUser'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'user_dashboard'
LOGOUT_REDIRECT_URL = 'login'


# ------------------------------------------------------------------
# Session security
# ------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7   # 1 week


# ------------------------------------------------------------------
# REST Framework
# ------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
}


# ------------------------------------------------------------------
# Third-party API keys — sourced entirely from environment
# ------------------------------------------------------------------
GROQ_API_KEY = env("GROQ_API_KEY")

# Tatum (Bitcoin withdrawals)
TATUM_API_KEY = env("TATUM_API_KEY")

TRONGRID_API_KEY = env("TRONGRID_API_KEY")
USDT_TRC20_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
TRON_PLATFORM_PRIVATE_KEY = env("TRON_PLATFORM_PRIVATE_KEY")
TRON_PLATFORM_ADDRESS = env("TRON_PLATFORM_ADDRESS")

ETHERSCAN_API_KEY = env("ETHERSCAN_API_KEY")
USDT_ERC20_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
ETH_RPC_URL = env("ETH_RPC_URL")
ETH_PLATFORM_PRIVATE_KEY = env("ETH_PLATFORM_PRIVATE_KEY")
ETH_PLATFORM_ADDRESS = env("ETH_PLATFORM_ADDRESS")

BTC_PLATFORM_ADDRESS = env("BTC_PLATFORM_ADDRESS")
BTC_PLATFORM_PRIVATE_KEY = env("BTC_PLATFORM_PRIVATE_KEY")

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'payment': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'kyc': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}