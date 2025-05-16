"""Settings for external service integrations."""

import os
from django.core.exceptions import ImproperlyConfigured

def get_env_variable(var_name):
    """Get environment variable or raise exception."""
    try:
        return os.environ[var_name]
    except KeyError:
        error_msg = f'Set the {var_name} environment variable'
        raise ImproperlyConfigured(error_msg)

# OpenRouter AI Settings
ENABLE_AI_PROCESSING = True
OPENROUTER_API_KEY = get_env_variable('OPENROUTER_API_KEY')

# VerifyMe Settings
VERIFYME_API_KEY = get_env_variable('VERIFYME_API_KEY')
VERIFYME_TEST_MODE = False  # Production mode

# Flutterwave Settings
FLUTTERWAVE_SECRET_KEY = get_env_variable('FLUTTERWAVE_SECRET_KEY')
FLUTTERWAVE_PUBLIC_KEY = get_env_variable('FLUTTERWAVE_PUBLIC_KEY')
FLUTTERWAVE_LOGO_URL = 'https://abiahub.ng/static/images/logo.png'
FLUTTERWAVE_TEST_MODE = False  # Production mode

# Africa's Talking Settings
AT_USERNAME = get_env_variable('AT_USERNAME')
AT_API_KEY = get_env_variable('AT_API_KEY')
AT_SENDER_ID = 'AbiaHub'  # Your registered sender ID
AT_TEST_MODE = False  # Production mode

# Cache settings for USSD session management
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': get_env_variable('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
            'MAX_CONNECTIONS': 1000,
            'PARSER_CLASS': 'redis.connection.HiredisParser',
        },
        'KEY_PREFIX': 'abiahub'
    }
} 