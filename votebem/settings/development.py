from .base import *
import os
from decouple import config

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-me')

# Allowed hosts for development
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0').split(',')

# Database for development (MariaDB in Docker with SQLite fallback)
from django.core.exceptions import ImproperlyConfigured
import pymysql

def get_database_config():
    """
    Try to connect to MariaDB first, fallback to SQLite if not available.
    """
    try:
        # Test MariaDB connection
        conn = pymysql.connect(
            host=config('DB_HOST', default='localhost'),
            port=int(config('DB_PORT', default='3306')),
            user=config('DB_USER', default='votebem_user'),
            password=config('DB_PASSWORD', default='votebem_dev_password'),
            database=config('DB_NAME', default='votebem_dev'),
            connect_timeout=5,
        )
        conn.close()

        # MariaDB is available
        return {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': config('DB_NAME', default='votebem_dev'),
                'USER': config('DB_USER', default='votebem_user'),
                'PASSWORD': config('DB_PASSWORD', default='votebem_dev_password'),
                'HOST': config('DB_HOST', default='localhost'),
                'PORT': config('DB_PORT', default='3306'),
                'OPTIONS': {
                    'charset': 'utf8mb4',
                    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                },
            }
        }
    except Exception:
        # MariaDB not available, use SQLite
        print("MariaDB not available, using SQLite database")
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }

DATABASES = get_database_config()

# Cache configuration (Redis in Docker with local memory fallback)
def get_cache_config():
    """
    Try to connect to Redis first, fallback to local memory cache if not available.
    """
    try:
        import redis
        r = redis.Redis.from_url(config('REDIS_URL', default='redis://localhost:6379/0'))
        r.ping()
        
        # Redis is available
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                },
                'KEY_PREFIX': 'votebem_dev',
                'TIMEOUT': 300,
            }
        }
    except (ImportError, Exception):
        # Redis not available, use local memory cache
        print("Redis not available, using local memory cache")
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'votebem_dev_cache',
                'TIMEOUT': 300,
            }
        }

CACHES = get_cache_config()

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Social Authentication Settings for Development
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'key': ''
        }
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SDK_URL': '//connect.facebook.net/{locale}/sdk.js',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'INIT_PARAMS': {'cookie': True},
        'FIELDS': [
            'id',
            'first_name',
            'last_name',
            'middle_name',
            'name',
            'name_format',
            'picture',
            'short_name',
            'email',
        ],
        'EXCHANGE_TOKEN': True,
        'LOCALE_FUNC': 'path.to.callable',
        'VERIFIED_EMAIL': False,
        'VERSION': 'v17.0',
        'APP': {
            'client_id': os.environ.get('FACEBOOK_APP_ID', ''),
            'secret': os.environ.get('FACEBOOK_APP_SECRET', ''),
            'key': ''
        }
    }
}

# Debug toolbar for development
if DEBUG:
    INSTALLED_APPS += [
        'debug_toolbar',
        'django_extensions',
    ]
    
    MIDDLEWARE += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]
    
    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]

# Logging for development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}

# Remote debugging for development (disabled by default to avoid port conflicts)
# To enable remote debugging, uncomment the lines below:
# import debugpy
# debugpy.listen(('0.0.0.0', 5678))
# print('Development debugpy listening on port 5678')