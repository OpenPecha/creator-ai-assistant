"""
Django settings for the Creator AI Assistant backend.

All environment-specific behavior is driven by a `.env` file (see `.env.example`)
so the same code runs locally and on EC2 — only the env values change.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

_INSECURE_SECRET_DEFAULT = "django-insecure-dev-key-change-me-in-production"

# --- Environment ------------------------------------------------------------
env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# "local" or "production"
ENV = env("ENV", default="local")
IS_PRODUCTION = ENV == "production"

SECRET_KEY = env("DJANGO_SECRET_KEY", default=_INSECURE_SECRET_DEFAULT)
DEBUG = env.bool("DJANGO_DEBUG", default=not IS_PRODUCTION)

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)

# --- Project-specific config ------------------------------------------------
# GitHub repo that holds the Bodhisattva Challenge content ("owner/repo-name").
# The backend fetches files directly from GitHub so no local clone is needed.
GITHUB_REPO = env("GITHUB_REPO", default="")
GITHUB_BRANCH = env("GITHUB_BRANCH", default="main")
# Optional — raises GitHub API rate limit from 60 to 5000 req/hour.
# Only the Git Trees API is called (once per server start); raw file fetches
# are not subject to the API rate limit regardless.
GITHUB_TOKEN = env("GITHUB_TOKEN", default="")

# Gemini (model ids are configurable; confirm current ids in the Gemini docs).
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_TEXT_MODEL = env("GEMINI_TEXT_MODEL", default="gemini-3.1-flash-lite")
GEMINI_TTS_MODEL = env("GEMINI_TTS_MODEL", default="gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = env("GEMINI_TTS_VOICE", default="Algenib")
# Natural-language delivery direction prepended to the script for TTS (Gemini
# supports style prompts). Keeps narration upbeat, warm, and clear for
# short-form social video (TikTok / Instagram Reels).
GEMINI_TTS_STYLE = env(
    "GEMINI_TTS_STYLE",
    default=(
        "Narrate the following in a neutral American accent. Speak fast — this "
        "is a TikTok voiceover, not a meditation. Keep the energy high, warm, "
        "and confident. Punchy delivery: short sentences land crisply, no "
        "dramatic pauses, no slow build-ups. Sound like a real person who is "
        "excited to share something, not a narrator reading aloud."
    ),
)

# --- Applications -----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "assistant",
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
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ---------------------------------------------------------------
# Default SQLite is used only by Django's built-in admin/sessions.
# This project defines no custom models and persists no app data in v1.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N -------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static & media ---------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- CORS -------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)

# --- DRF --------------------------------------------------------------------
# Throttling protects the (unauthenticated) Gemini-backed endpoints from abuse
# that would burn the API budget. Rates are configurable via .env.
# NOTE: throttle counters use Django's cache. The default LocMemCache is
# per-process, so with multiple gunicorn workers the effective limit is
# rate × workers. For accurate limits in production, configure a shared cache
# (Redis/Memcached).
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/min"),
        "generate": env("THROTTLE_GENERATE", default="20/min"),
    },
}

# --- Production hardening ---------------------------------------------------
if IS_PRODUCTION:
    # Fail fast on misconfiguration rather than silently running insecure.
    if DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_DEBUG must be False in production. Set ENV=production and "
            "DJANGO_DEBUG=false in the server .env."
        )
    if SECRET_KEY == _INSECURE_SECRET_DEFAULT:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a unique secret value in production."
        )

    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
