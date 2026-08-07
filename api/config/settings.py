"""
SkilRize API settings.

One settings module, driven entirely by environment variables — the report's
Section 27.1 rule: no environment-specific code branches, configuration through
env and a managed secret store only.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ENVIRONMENT = config("ENVIRONMENT", default="local")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")


# --- Applications ----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_celery_beat",
    # SkilRize
    "core",
    "accounts",
    "marketplace",
    "contracts",
    "gigs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Sets the per-request scope and audit context. Must run after auth so the
    # authenticated user is available.
    "core.middleware.RequestContextMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# --- Data ------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="skilrize"),
        "USER": config("POSTGRES_USER", default="skilrize"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="skilrize"),
        "HOST": config("POSTGRES_HOST", default="localhost"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}


# --- Authentication --------------------------------------------------------

# Argon2id first (report Section 6.1), with cost factors pinned in
# accounts.hashers rather than inherited from Django's shifting defaults. The
# remaining hashers exist only so that legacy hashes can still be verified and
# transparently upgraded on next login.
PASSWORD_HASHERS = [
    "accounts.hashers.SkilRizeArgon2Hasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

#: Floor for a new password. Raising this is safe at any time — existing
#: passwords are unaffected until their next change.
PASSWORD_MIN_LENGTH = config("PASSWORD_MIN_LENGTH", default=12, cast=int)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": PASSWORD_MIN_LENGTH},
    },
    # ~20k breached passwords, checked before composition so the clearest
    # failure is the one reported first.
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    # All four character classes, then the patterns people fall back on when a
    # composition rule forces variety they did not want.
    {"NAME": "accounts.validators.ComplexityValidator"},
    {"NAME": "accounts.validators.PredictabilityValidator"},
]

# --- Brute-force lockout ---------------------------------------------------
# Two independent budgets, because the two attacks look nothing alike.
#
# Per account: bounds what any one account can absorb no matter how many
# addresses the guesses arrive from. This is the credential-stuffing defence.
LOGIN_MAX_ATTEMPTS = config("LOGIN_MAX_ATTEMPTS", default=5, cast=int)
LOGIN_LOCKOUT_SECONDS = config("LOGIN_LOCKOUT_SECONDS", default=1800, cast=int)  # 30 minutes

# Per source address: bounds a single origin spraying many *different* accounts,
# which the per-account budget above never sees because no one account reaches
# its limit. Counts failures only — a shared office or campus NAT can produce a
# steady trickle of successful logins from one address quite legitimately, and
# counting those would lock out the building.
LOGIN_IP_MAX_FAILURES = config("LOGIN_IP_MAX_FAILURES", default=10, cast=int)
LOGIN_IP_WINDOW_SECONDS = config("LOGIN_IP_WINDOW_SECONDS", default=600, cast=int)  # 10 minutes
LOGIN_IP_BLOCK_SECONDS = config("LOGIN_IP_BLOCK_SECONDS", default=3600, cast=int)  # 1 hour

# --- New-device verification -----------------------------------------------
# An account with no authenticator enrolled must prove control of its inbox
# before a device it has never used gets a session. This is what stops a stolen
# password on its own from being enough for the users who never turned 2FA on —
# which is most of them.
#
# It is a switch rather than a constant so it can be turned off deliberately if
# outbound mail is down and the alternative is locking everyone out. Default on.
REQUIRE_NEW_DEVICE_VERIFICATION = config("REQUIRE_NEW_DEVICE_VERIFICATION", default=True, cast=bool)

# --- New-device cool-off ---------------------------------------------------
# A password that has just been used from an unrecognised device is the exact
# signature of a freshly stolen credential. Rather than block the session — the
# legitimate case is common and blocking it is hostile — the device may browse
# everything and simply cannot move money until the window closes. That leaves
# the real user a couple of hours to read the alert email and revoke.
DEVICE_COOLOFF_SECONDS = config("DEVICE_COOLOFF_SECONDS", default=7200, cast=int)  # 2 hours

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.auth.CookieJWTAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    # Strict limits on the endpoints that are actually attacked, generous
    # elsewhere (Section 7.1).
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "240/minute",
        "login": "10/minute",
        "signup": "5/hour",
        "otp": "5/minute",
        "password_reset": "5/hour",
    },
    "EXCEPTION_HANDLER": "core.middleware.exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    # Rotation plus reuse detection is implemented in accounts.auth; SimpleJWT's
    # own blacklist app is deliberately not used because it cannot invalidate a
    # whole token family on reuse.
    "ROTATE_REFRESH_TOKENS": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Refresh tokens live in Secure/HttpOnly/SameSite cookies on web; access tokens
# are never written to localStorage (Section 6.3).
REFRESH_COOKIE_NAME = "skilrize_refresh"
COOKIE_SECURE = config("COOKIE_SECURE", default=not DEBUG, cast=bool)
COOKIE_DOMAIN = config("COOKIE_DOMAIN", default="") or None
COOKIE_SAMESITE = "Lax"

if not DEBUG:
    # An environment variable may relax this locally over plain http, but it
    # must never be able to relax it in a deployed environment. `COOKIE_SECURE`
    # is the single setting most likely to reach production by being copied out
    # of somebody's local .env, and the cost of getting it wrong is every
    # session token readable by anything on the path.
    COOKIE_SECURE = True


# --- Security --------------------------------------------------------------

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = COOKIE_SECURE
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"
# The CSRF cookie is read by the web client to echo the token back in a header,
# so it cannot be HttpOnly. That is the documented double-submit design and is
# safe as long as the value is only ever *reflected*, never trusted on its own.
CSRF_COOKIE_HTTPONLY = False

# --- Request limits --------------------------------------------------------
# Django's defaults allow a 2.5 MB form body and 1000 fields. Neither is needed
# here — uploads go through the dedicated endpoint with its own ceiling — and
# both are cheap denial-of-service surface: parsing is done before any view
# runs, so an unauthenticated request can spend server memory for free.
DATA_UPLOAD_MAX_MEMORY_SIZE = 1 * 1024 * 1024  # 1 MB of JSON is already generous
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 10
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # larger files spool to disk

# --- Interim admin ---------------------------------------------------------
# Django admin is internal tooling until the custom console replaces it. Moving
# it off the default path is not a security control on its own, but it removes
# the account from every commodity scanner's first request, which is most of
# the noise in the auth logs.
ADMIN_URL = config("ADMIN_URL", default="admin/")

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# --- Files -----------------------------------------------------------------

# Nothing user-uploaded is served from the application origin. Files live in
# private storage and are reached only through short-lived signed URLs
# (Section 7.2).
STORAGE_BACKEND = config("STORAGE_BACKEND", default="local")
STORAGE_ROOT = BASE_DIR / config("STORAGE_ROOT", default=".storage")
FILE_SIGNING_KEY = config("FILE_SIGNING_KEY", default=SECRET_KEY)
# Rotatable independently of SECRET_KEY: rotating the session signing key must
# not make every encrypted identity document unreadable.
FIELD_ENCRYPTION_KEY = config("FIELD_ENCRYPTION_KEY", default=SECRET_KEY)
FILE_URL_TTL_SECONDS = 300
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB, per Section 6.2 step 5

# Antivirus. Point this at a clamd instance and every upload is streamed to it
# before it can be downloaded. Leaving it unset is only viable with DEBUG on —
# core.tasks refuses to mark anything clean without a scanner otherwise.
CLAMAV_HOST = config("CLAMAV_HOST", default="")
CLAMAV_PORT = config("CLAMAV_PORT", default=3310, cast=int)
CLAMAV_TIMEOUT = config("CLAMAV_TIMEOUT", default=30, cast=int)
# When true and no scanner is reachable, uploads are quarantined rather than
# passed. Keyed off DEBUG at import time rather than read at call time, because
# Django's test runner forces DEBUG off and would otherwise turn every suite
# into a fail-closed run against a scanner that was never meant to be there.
REQUIRE_FILE_SCANNER = config("REQUIRE_FILE_SCANNER", default=not DEBUG, cast=bool)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# --- Email -----------------------------------------------------------------

EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="SkilRize <no-reply@skilrize.com>")


# --- Async -----------------------------------------------------------------

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# Notifications are always queued, never sent inline with a web request
# (Section 24).
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=DEBUG, cast=bool)


# --- Locale ----------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Logging ---------------------------------------------------------------
# Structured, with a correlation id per request. No secrets, tokens, or full
# personal records (Section 7.6).

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_context": {"()": "core.middleware.RequestContextFilter"}},
    "formatters": {
        "structured": {
            "format": (
                '{{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
                '"request_id":"%(request_id)s","message":"%(message)s"}}'
            )
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["request_context"],
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Security events (cross-tenant denials, brute force, privilege
        # escalation attempts) get their own logger so alerting can target it.
        "skilrize.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
