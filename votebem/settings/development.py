from .base import *
import os
from decouple import config
import pymysql
try:
    # Permite uso de PyMySQL como substituto do MySQLdb em desenvolvimento
    pymysql.install_as_MySQLdb()
except Exception:
    pass
from votebem.utils.devlog import dev_log  # Development log utility

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-me')

# Allowed hosts for development
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0').split(',')

# OPENAI API Key for development: centralize here for consistent access
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or config('OPENAI_API_KEY', default='')

# Default embedding model used by Chroma's OpenAIEmbeddingFunction
# This can be overridden via environment variable OPENAI_EMBED_MODEL.
OPENAI_EMBED_MODEL = os.environ.get('OPENAI_EMBED_MODEL', 'text-embedding-3-small')

# LLM model for OpenAI usage in development.
# Enforced globally to ensure consistent behavior and costs.
# Do NOT override via environment; always use 'gpt-4o-mini'.
OPENAI_LLM_MODEL = 'gpt-4o-mini'

# Explicitly keep development HTTP-only to avoid accidental HTTPS redirects
# and HSTS persistence when testing locally.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = None
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Database for development (MariaDB in Docker with SQLite fallback)
from django.core.exceptions import ImproperlyConfigured
import pymysql

def get_database_config():
    """
    Development DB selection:
    - Prefer connecting to MariaDB on 127.0.0.1 (container port mapping).
    - Try env-provided host next (e.g., 'db' or custom), then 'localhost'.
    - Fall back to SQLite if MariaDB is not reachable. This is intentional
      for local host runs when the container is down.
    """
    name = config('DB_NAME', default='votebem_db')
    user = config('DB_USER', default='votebem_user')
    password = config('DB_PASSWORD', default='votebem_dev_password')
    port = int(config('DB_PORT', default='3306'))
    host_env = config('DB_HOST', default='127.0.0.1')

    # Build candidate hosts (prefer 127.0.0.1 outside Docker)
    candidates = []
    for h in ['127.0.0.1', host_env, 'localhost']:
        if h and h not in candidates:
            candidates.append(h)

    chosen_host = None
    last_error = None

    for h in candidates:
        try:
            conn = pymysql.connect(
                host=h,
                port=port,
                user=user,
                password=password,
                database=name,
                connect_timeout=4,
            )
            conn.close()
            chosen_host = h
            break
        except Exception as e:
            last_error = e
            continue

    if chosen_host:
        dev_log(f"Using MariaDB at {chosen_host}:{port}")
        return {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': name,
                'USER': user,
                'PASSWORD': password,
                'HOST': chosen_host,
                'PORT': str(port),
                'OPTIONS': {
                    'charset': 'utf8mb4',
                    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                },
            }
        }

    # MariaDB not available — fall back to SQLite for development
    dev_log(
        "MariaDB not available, using SQLite database.",
        "Last error:", str(last_error) if last_error else "(none)"
    )
    return {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

DATABASES = get_database_config()

# Cache configuration (Valkey/Redis in Docker with robust localhost fallback)
def get_cache_config():
    """
    Development cache selection logic with robust Valkey/Redis detection.

    Rationale:
    - In local dev, Compose service names like "redis" or "valkey" are not
      resolvable from the host (Windows/POSIX). The containers publish port
      6379 to 127.0.0.1, so the host must connect to localhost.
    - Some environments may define `REDIS_URL` pointing to a service name.
      We proactively attempt multiple candidate URLs, prioritizing environment
      values, then known localhost defaults. If none succeed, we fall back to
      Django's in‑memory cache to keep development productive.
    - If `REDIS_PASSWORD` is defined, we include it in the URL transparently.
    """

    try:
        import redis

        # Gather environment configuration
        env_url = os.environ.get('REDIS_URL')  # raw env (decouple mirrors this)
        host = os.environ.get('REDIS_HOST', '127.0.0.1')
        port = os.environ.get('REDIS_PORT', '6379')
        db = os.environ.get('REDIS_DB', '0')
        pwd = os.environ.get('REDIS_PASSWORD')  # optional

        # Helper to build a URL with optional password
        def build_url(h: str, p: str, d: str, password: str | None) -> str:
            if password:
                return f"redis://:{password}@{h}:{p}/{d}"
            return f"redis://{h}:{p}/{d}"

        # Candidate URLs to try (ordered by priority)
        candidates: list[str] = []

        # 1) Take the env/decouple URL if provided
        if env_url:
            candidates.append(env_url)

        # 2) Compose a URL from host/port/db/password envs (defaults favor localhost)
        candidates.append(build_url(host, port, db, pwd))

        # 3) Explicit localhost fallbacks
        candidates.append(build_url('127.0.0.1', '6379', db, pwd))
        candidates.append(build_url('localhost', '6379', db, pwd))

        chosen_url = None
        last_error = None

        # Iterate candidates and pick the first that responds to PING
        for url in candidates:
            try:
                client = redis.Redis.from_url(url)
                # Use a short timeout to avoid slowing startup if wrong
                client.ping()
                chosen_url = url
                break
            except Exception as e:
                last_error = e
                continue

        if chosen_url:
            # Valkey/Redis is available — configure Django RedisCache backend.
            dev_log(f"Using Redis cache at {chosen_url}")
            return {
                'default': {
                    'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                    'LOCATION': chosen_url,
                    # Keep dev‑friendly defaults; avoid external dependencies.
                    'KEY_PREFIX': 'votebem_dev',
                    'TIMEOUT': 300,
                }
            }

        # No candidates succeeded, fall back to local memory cache.
        dev_log(
            "Redis not available, using local memory cache",
            "Last error:", str(last_error) if last_error else "(none)"
        )
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'votebem_dev_cache',
                'TIMEOUT': 300,
            }
        }
    except ImportError:
        # `redis` Python client not installed — remain productive in dev.
        dev_log("redis package not installed; using local memory cache")
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

# Embedding provider selection and local model configuration for development
# EMBEDDING_PROVIDER: 'openai' (default) or 'local'
# LOCAL_EMBED_MODEL: sentence-transformers model when using local provider
# CHROMA_PERSIST_PATH: if set non-empty, use chromadb.PersistentClient(path=...)
EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER') or config('EMBEDDING_PROVIDER', default='local')
LOCAL_EMBED_MODEL = os.environ.get('LOCAL_EMBED_MODEL') or config('LOCAL_EMBED_MODEL', default='all-MiniLM-L6-v2')
CHROMA_PERSIST_PATH = os.environ.get('CHROMA_PERSIST_PATH') or config('CHROMA_PERSIST_PATH', default='')