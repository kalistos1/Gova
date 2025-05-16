

import os
from pathlib import Path
from django.contrib import messages
from datetime import timedelta
import logging
from decouple import config, Csv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-!y%r!cc#$$8a1k$a9$6%g#a=jjo#c9+9pynlvx+%8&*sesa9(&'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [".vercel.app"]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.gis',
    
    # Third-party apps
   
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'axes',
    # 'debug_toolbar',
    # 'whitenoise.runserver_nostatic',
    

    # Local apps
    'accounts',
    'core',
    'reports',
    # 'grants',
    'api',
    'proposals',
    'services',
    'engagement',
]



MIDDLEWARE = [
    # Security middleware
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'csp.middleware.CSPMiddleware',
    'axes.middleware.AxesMiddleware',
    
    # Django middleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
 
    # API middleware

    'api.middleware.AuditLogMiddleware',
    
    # Core middleware
    'core.middleware.LogRequestMiddleware',
    'core.middleware.RoleBasedAccessMiddleware',
    
    # Debug middleware (only in development)
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
]

ROOT_URLCONF = 'gova.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        #   'DIRS': [ BASE_DIR / 'templates'],
       
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gova.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.contrib.gis.db.backends.postgis',
#         'NAME': config('DB_NAME'),
#         'USER': config('DB_USER'),
#         'PASSWORD': config('DB_PASSWORD'),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#         'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
#         'OPTIONS': {
#             'sslmode': config('DB_SSL_MODE', default='require'),
#             'keepalives': 1,
#             'keepalives_idle': 30,
#             'keepalives_interval': 10,
#             'keepalives_count': 5,
#         },
#         'POOL': {
#             'CONN_MIN': config('DB_POOL_MIN', default=5, cast=int),
#             'CONN_MAX': config('DB_POOL_MAX', default=20, cast=int),
#             'CONN_TIMEOUT': config('DB_POOL_TIMEOUT', default=30, cast=int),
#             'CONN_RETRY': config('DB_POOL_RETRY', default=1, cast=int),
#         },
#     }
# }


# Database connection pooling
DATABASE_CONNECTION_POOLING = True

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        *(['rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else []),
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'api.exceptions.custom_exception_handler',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    
    'JTI_CLAIM': 'jti',
    
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# Security Settings
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CORS Settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='https://abiahub.ng',
    cast=Csv()
)
CORS_ALLOW_CREDENTIALS = True

# CSP Settings
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:", "https:")

# Django Axes
AXES_FAILURE_LIMIT = 5
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = 1  # 1 hour

AXES_LOCKOUT_TEMPLATE = 'accounts/lockout.html'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Authentication
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'accounts.backend.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_USER_MODEL = 'accounts.User'

# Static files (CSS, JavaScript, Images)
# STATIC_URL = '/static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_DIRS = [BASE_DIR / 'static']


STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR/ "static", "./static/",
]
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Settings
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = config('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='AbiaHub <noreply@abiahub.gov.ng>')

# External API Keys
OPENROUTER_API_KEY = config('OPENROUTER_API_KEY')
VERIFYME_API_KEY = config('VERIFYME_API_KEY')
FLUTTERWAVE_API_KEY = config('FLUTTERWAVE_API_KEY')
AFRICAS_TALKING_API_KEY = config('AFRICAS_TALKING_API_KEY')
AFRICAS_TALKING_USERNAME = config('AFRICAS_TALKING_USERNAME')

# Stellar Blockchain Settings
STELLAR_API_URL = config('STELLAR_API_URL', default='https://horizon.stellar.org')
STELLAR_API_KEY = config('STELLAR_API_KEY')
STELLAR_SOURCE_ACCOUNT = config('STELLAR_SOURCE_ACCOUNT')
STELLAR_NETWORK = config('STELLAR_NETWORK', default='public')

# Sentry Error Tracking
if not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=config('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=True,
        environment=config('ENVIRONMENT', default='production')
    )

# Debug Toolbar
# if DEBUG:
#     INTERNAL_IPS = ['127.0.0.1']
#     DEBUG_TOOLBAR_CONFIG = {
#         'SHOW_TOOLBAR_CALLBACK': lambda request: True,
#     }

# # Logging Configuration
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'formatters': {
#         'verbose': {
#             'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
#             'style': '{',
#         },
#     },
#     'handlers': {
#         'file': {
#             'level': 'INFO',
#             'class': 'logging.FileHandler',
#             'filename': BASE_DIR / 'logs/abiahub.log',
#             'formatter': 'verbose',
#         },
#         'console': {
#             'level': 'DEBUG',
#             'class': 'logging.StreamHandler',
#             'formatter': 'verbose',
#         },
#     },
#     'loggers': {
#         'django': {
#             'handlers': ['file', 'console'],
#             'level': 'INFO',
#             'propagate': True,
#         },
#         'abiahub': {
#             'handlers': ['file', 'console'],
#             'level': 'DEBUG' if DEBUG else 'INFO',
#             'propagate': True,
#         },
#     },
# }

# Role-based access control
ROLE_BASED_ACCESS = {
    'reports': {
        'GET': ['LGA_OFFICIAL', 'STATE_OFFICIAL', 'ADMIN'],
        'POST': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'DELETE': ['STATE_OFFICIAL', 'ADMIN'],
    },
    'grants': {
        'GET': ['LGA_OFFICIAL', 'STATE_OFFICIAL', 'ADMIN'],
        'POST': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'DELETE': ['STATE_OFFICIAL', 'ADMIN'],
    },
    'proposals': {
        'GET': ['LGA_OFFICIAL', 'STATE_OFFICIAL', 'ADMIN', 'CITIZEN'],
        'POST': ['LGA_OFFICIAL', 'STATE_OFFICIAL', 'CITIZEN'],
        'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'DELETE': ['STATE_OFFICIAL', 'ADMIN'],
    },
    'services': {
        'GET': ['LGA_OFFICIAL', 'STATE_OFFICIAL', 'ADMIN', 'CITIZEN'],
        'POST': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'DELETE': ['STATE_OFFICIAL', 'ADMIN'],
    },
    'engagement': {
        'GET': ['LGA_OFFICIAL', 'STATE_OFFICIAL', 'ADMIN', 'CITIZEN'],
        'POST': ['LGA_OFFICIAL', 'STATE_OFFICIAL', 'CITIZEN'],
        'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
        'DELETE': ['STATE_OFFICIAL', 'ADMIN'],
    },
    'admin': {
        'GET': ['ADMIN'],
        'POST': ['ADMIN'],
        'PATCH': ['ADMIN'],
        'DELETE': ['ADMIN'],
    }
}

# Frontend URLs
FRONTEND_URL = config('FRONTEND_URL', default='https://abiahub.ng')
PASSWORD_RESET_URL = f'{FRONTEND_URL}/reset-password'
EMAIL_VERIFICATION_URL = f'{FRONTEND_URL}/verify-email'

# Password Reset Settings
PASSWORD_RESET_TIMEOUT = 3600  # 1 hour
VERIFICATION_TOKEN_TIMEOUT = 86400  # 24 hours

# Admin Notification Settings
ADMIN_EMAIL = config('ADMIN_EMAIL', default='admin@abiahub.gov.ng')
ADMIN_NOTIFICATION_ENABLED = True
ADMIN_NOTIFICATION_BATCH_SIZE = 10

# Rate Limiting
RATE_LIMITS = {
    'default': '100/hour',
    'auth': {
        'nin-verify': '5/hour',
        'token-refresh': '30/minute',
        'password-reset': '3/hour',
        'password-change': '5/hour',
        'login': '10/hour'
    }
}

# Blocked NIN numbers (test numbers)
BLOCKED_NIN_NUMBERS = [
    '00000000000',
    '11111111111',
    '99999999999'
]

# Cache settings
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
            'MAX_CONNECTIONS': 1000,
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
            'COMPRESSOR_CLASS': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'abiahub',
        'TIMEOUT': 300,  # 5 minutes default timeout
    },
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_SESSION_URL', default='redis://127.0.0.1:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
        },
        'KEY_PREFIX': 'session',
        'TIMEOUT': 86400,  # 1 day
    },
    'throttling': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_THROTTLE_URL', default='redis://127.0.0.1:6379/3'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
        },
        'KEY_PREFIX': 'throttle',
        'TIMEOUT': 3600,  # 1 hour
    }
}

# Cache configuration
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = 'abiahub'
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'

# Cache invalidation settings
CACHE_INVALIDATION_TIMEOUT = 60  # 1 minute
CACHE_VERSIONING = True
