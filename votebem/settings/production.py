from .base import *
import os
from pathlib import Path
try:
    from decouple import Config, RepositoryEnv, config as _config_fn
    ENV_FILE_PATH = os.environ.get('DJANGO_ENV_PATH') or str(Path(BASE_DIR) / '.env')
    if ENV_FILE_PATH and os.path.exists(ENV_FILE_PATH) and os.access(ENV_FILE_PATH, os.R_OK):
        config = Config(RepositoryEnv(ENV_FILE_PATH))
    else:
        config = _config_fn
except Exception:
    from decouple import config

# Sites framework: override SITE_ID via environment to match deployed domain.
# Base sets SITE_ID=1; in production you likely want it to correspond to
# 'votebem.online' or 'www.votebem.online'.
try:
    SITE_ID = config('SITE_ID', default=SITE_ID, cast=int)  # override base
except Exception:
    try:
        SITE_ID = int(os.environ.get('SITE_ID', str(SITE_ID)))
    except Exception:
        # Keep base value if conversion fails
        SITE_ID = SITE_ID

# SECURITY WARNING: don't run with debug turned on in production!
# Wagner: alterar para False em produção
DEBUG = config('DEBUG', default=True, cast=bool)

# SECURITY WARNING: keep the secret key used in production secret!
# Read from environment/.env; do not ship hardcoded secrets in repository.
SECRET_KEY = config('SECRET_KEY')

# Allowed hosts
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Proxy/host handling
USE_X_FORWARDED_HOST = config('USE_X_FORWARDED_HOST', default=True, cast=bool)

# CSRF trusted origins
# Sanitize and normalize values that may include stray quotes/backticks/spaces.
_origins_raw = config('CSRF_TRUSTED_ORIGINS', default='')

def _clean_origin(val: str) -> str:
    """
    Normalize an origin string by:
    - trimming whitespace
    - stripping stray quotes/backticks
    - returning the cleaned value
    This function does not add schemes; use normalization below if needed.
    """
    v = (val or '').strip()
    # Remove common stray characters from envs like: `https://example.com` or ' https://... '
    v = v.strip("`'")
    # Also collapse internal excessive spaces around the value
    return v.strip()

raw_list = [_clean_origin(o) for o in _origins_raw.split(',')] if _origins_raw.strip() else []
CSRF_TRUSTED_ORIGINS = [o for o in raw_list if o]

# If env did not provide, build from ALLOWED_HOSTS with http/https variants
if not CSRF_TRUSTED_ORIGINS:
    for _h in ALLOWED_HOSTS:
        _h = (_h or '').strip()
        if not _h:
            continue
        if _h.startswith('http://') or _h.startswith('https://'):
            CSRF_TRUSTED_ORIGINS.append(_h)
        else:
            CSRF_TRUSTED_ORIGINS.append(f'http://{_h}')
            CSRF_TRUSTED_ORIGINS.append(f'https://{_h}')

# Defensive merge: ensure HTTPS origins for all ALLOWED_HOSTS are present
try:
    _origins_set = set()
    # Start with cleaned env-provided
    for o in CSRF_TRUSTED_ORIGINS:
        o = _clean_origin(o)
        if not o:
            continue
        # Ensure scheme present; prefer https
        if o.startswith('http://') or o.startswith('https://'):
            _origins_set.add(o)
        else:
            _origins_set.add(f'https://{o}')
            _origins_set.add(f'http://{o}')

    # Merge HTTPS origins for all ALLOWED_HOSTS
    for _h in ALLOWED_HOSTS:
        _h = _clean_origin(_h)
        if not _h:
            continue
        # Normalize hosts that may already include schemes
        if _h.startswith('http://') or _h.startswith('https://'):
            from urllib.parse import urlparse
            _parsed = urlparse(_h)
            _host = _parsed.netloc or _parsed.path or _h.replace('https://','').replace('http://','')
        else:
            _host = _h
        _origins_set.add(f'https://{_host}')

    CSRF_TRUSTED_ORIGINS = sorted(_origins_set)
except Exception:
    # Never break settings import due to origin normalization
    CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS

# Database (MariaDB/MySQL)
# All sensitive values (passwords) are read from environment/.env only.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='votebem_db'),
        'USER': config('DB_USER', default='votebem_user'),
        'PASSWORD': config('DB_PASSWORD'),
        # Hostname for DB. In Docker, 'db' is resolvable via Docker DNS.
        # On host Windows/macOS dev runs (outside Docker), 'db' may NOT resolve.
        # We will resolve and fallback to '127.0.0.1' if DNS fails, so local
        # runs using production settings don't crash with Unknown host 'db'.
        'HOST': config('DB_HOST', default='db'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 60,
    }
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        # Prefer os.environ for Docker overrides, then config from file, then default
        'LOCATION': os.environ.get('REDIS_URL') or config('REDIS_URL', default='redis://valkey:6379/0'),
        'KEY_PREFIX': 'votebem',
        'TIMEOUT': 300,
    }
}

# Session engine (configurable)
# Use cache-backed sessions by default (requires Redis). To avoid 500s when Redis
# is unavailable or misconfigured, you can set SESSION_ENGINE to 'db' in the env.
_session_backend = config('SESSION_ENGINE', default='cache').strip().lower()
if _session_backend == 'db':
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'
    SESSION_CACHE_ALIAS = None
else:
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'
STATICFILES_DIRS = []  # No additional static dirs in production, only STATIC_ROOT
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
# compose maps the host folder with real files to the container path:
#   docker-compose.yml:52-54 maps '/dados/votebem/votebem/media' to '/app/media' .
# Nginx runs on the host, its location /media/ must alias the host path. 
#   So, in config file /etc/nginx/sites-available/votebem:
#       alias /dados/votebem/votebem/media/; (keep trailing slash)
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# HTTPS settings (enable when using SSL)
# We unconditionally enable SECURE_PROXY_SSL_HEADER because we are always behind Nginx in production.
# This ensures Django correctly detects HTTPS requests via the X-Forwarded-Proto header.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if config('USE_HTTPS', default=False, cast=bool):
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Force allauth to use HTTPS for callback URLs
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'

# CORS settings
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='').split(',')
CORS_ALLOW_CREDENTIALS = True

SOCIALACCOUNT_LOGIN_ON_GET = True


# Logging
import logging.handlers

# Container-friendly logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'allauth': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'votebem': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'gunicorn': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'gunicorn.error': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'gunicorn.access': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Optional file logging if logs directory is writable
LOG_DIR = '/app/logs'
try:
    # Only add file logging if we can create the directory and it's writable
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    # Test if we can write to the directory
    test_file = os.path.join(LOG_DIR, 'test_write.tmp')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
    # If we get here, file logging is possible
    LOGGING['handlers']['file'] = {
        'level': 'INFO',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': os.path.join(LOG_DIR, 'django.log'),
        'formatter': 'verbose',
        'maxBytes': 1024*1024*10,  # 10MB
        'backupCount': 5,
    }
    # Add file handler to loggers
    for logger_name in ['django', 'votebem', 'gunicorn', 'gunicorn.error']:
        if logger_name in LOGGING['loggers']:
            LOGGING['loggers'][logger_name]['handlers'].append('file')
    LOGGING['root']['handlers'].append('file')
except (OSError, IOError, PermissionError):
    # If file logging fails, just use console logging
    # This prevents the container from failing to start
    pass

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@votebem.com')

# Social Authentication Settings
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
            'client_id': config('GOOGLE_CLIENT_ID', default=''),
            'secret': config('GOOGLE_CLIENT_SECRET', default=''),
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
            'client_id': config('FACEBOOK_APP_ID', default=''),
            'secret': config('FACEBOOK_APP_SECRET', default=''),
            'key': ''
        }
    }
}

# Social login rendering control
# --------------------------------
# Make this configurable via environment/.env so you can enable social login
# without changing code. Default False in production for safe deployments.
try:
    SOCIAL_LOGIN_ENABLED = config('SOCIAL_LOGIN_ENABLED', default=False, cast=bool)
except Exception:
    # If python-decouple is unavailable or misconfigured, fall back to env var.
    SOCIAL_LOGIN_ENABLED = (
        str(os.environ.get('SOCIAL_LOGIN_ENABLED', '')).strip().lower() in ('1', 'true', 'yes')
    )

# Remote debugging configuration
if config('ENABLE_REMOTE_DEBUG', default=False, cast=bool):
    import debugpy
    debugpy.listen(('0.0.0.0', 5678))
    from votebem.utils.devlog import dev_log  # Dev logger for consistency
    dev_log('Debugpy listening on port 5678')

# Performance optimizations
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# Add whitenoise middleware
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
MIDDLEWARE.insert(0, 'corsheaders.middleware.CorsMiddleware')

# Add CORS to installed apps
INSTALLED_APPS += [
    'corsheaders',
    'django_extensions',
]

# --- Runtime DNS fallback for DB and Redis when running outside Docker ---
# Rationale
# --------
# - In production Compose, service names like 'db' and 'redis' resolve via Docker DNS.
# - When someone runs manage.py with production settings on the HOST (Windows/macOS),
#   those names do not resolve and lead to errors like:
#     OperationalError: (2005, "Unknown server host 'db' (11001)")
# - To make production settings more robust for occasional host-side executions
#   (migrations, test runs, quick checks), we apply a lightweight DNS resolution
#   check and fallback to localhost if needed.
try:
    import socket
    # Resolve and fallback DB host
    _db_host = DATABASES['default'].get('HOST') or 'db'
    try:
        # Attempt DNS resolution; if it fails, fallback to loopback.
        socket.gethostbyname(_db_host)
    except socket.gaierror:
        DATABASES['default']['HOST'] = '127.0.0.1'

    # Resolve and fallback Redis host within LOCATION URL
    from urllib.parse import urlparse
    _cache_loc = CACHES['default'].get('LOCATION', '')
    if _cache_loc:
        parsed = urlparse(_cache_loc)
        host = parsed.hostname or 'redis'
        try:
            socket.gethostbyname(host)
        except socket.gaierror:
            # Rebuild URL with localhost preserving scheme/port/db
            port = parsed.port or 6379
            db = parsed.path or '/0'
            CACHES['default']['LOCATION'] = f"{parsed.scheme}://127.0.0.1:{port}{db}"
except Exception:
    # Fail-safe: never break settings import due to fallback logic.
    pass
LOGIN_URL = '/accounts/login/'

# Embedding provider and Chroma persistence configuration for production
EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER') or config('EMBEDDING_PROVIDER', default='openai')
LOCAL_EMBED_MODEL = os.environ.get('LOCAL_EMBED_MODEL') or config('LOCAL_EMBED_MODEL', default='all-MiniLM-L6-v2')
CHROMA_PERSIST_PATH = os.environ.get('CHROMA_PERSIST_PATH') or config('CHROMA_PERSIST_PATH', default='/dados/chroma')

# LLM model for OpenAI usage in production.
# Enforced globally to ensure consistent behavior and costs.
# Do NOT override via environment; always use 'gpt-4o-mini'.
OPENAI_LLM_MODEL = 'gpt-4o-mini'
