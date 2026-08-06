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
GITHUB_TOKEN = env("GITHUB_TOKEN", default="")
# Seconds to cache GitHub responses per process. Collapses the 5–14 outbound
# calls per day-load down to ~1 per file per window, keeping us well under
# GitHub's API rate limits. Higher = fewer calls but slower to reflect content
# pushes; 0 disables caching (always fetch fresh).
GITHUB_CACHE_TTL = env.int("GITHUB_CACHE_TTL", default=300)

# Separate GitHub repo the team reviews generated video ideas in, as an
# Obsidian vault ("owner/repo-name"). Deliberately its own repo/token (write
# access), never the read-only source-content repo/token above.
GITHUB_REVIEW_REPO = env("GITHUB_REVIEW_REPO", default="")
GITHUB_REVIEW_BRANCH = env("GITHUB_REVIEW_BRANCH", default="main")
GITHUB_REVIEW_TOKEN = env("GITHUB_REVIEW_TOKEN", default="")

# WeBuddhist plan integration — the public plan API supplies the "today's
# challenge" shareable image, and the share site hosts the per-day plan link.
# Each CHAPTER is published as its own separate WeBuddhist "plan" (its own plan
# id), and that plan numbers its days starting from 1 — not from the global
# day number (see assistant.services.content_loader.day_offset_in_chapter).
WEBUDDHIST_API_BASE = env("WEBUDDHIST_API_BASE", default="https://api.webuddhist.com")
WEBUDDHIST_SHARE_BASE = env("WEBUDDHIST_SHARE_BASE", default="https://webuddhist.com")
WEBUDDHIST_PLAN_IDS = {
    "english": {
        1: "9c1cb58d-a972-4473-94f1-779abc4a5a4c",
        2: "1bc0d23d-78b9-4907-921d-84708900c96e",
        3: "2b2c930c-03ef-4e14-ad1b-00721f6a0912",
        4: "9b5fedf5-e340-4842-8050-424a61d4ef27",
        5: "04c1ccc9-70b7-4b76-b1ef-cf58623c44ed",
        6: "8ef5db71-3339-4329-804d-4c3bf1ffee66",
        7: "26fbb443-2ec8-4e3f-b7ac-c8b2a082332c",
        8: "39ebc11e-33fd-41b0-a3e8-8923a66be7db",
        9: "99e0a175-9a24-4de9-81b5-54cd31ae1a31",
        10: "f5dac5c9-6392-4186-9ded-e6d4772aabb7",
    },
    "hindi": {
        1: "920d96b3-933b-42cd-8de1-0666b107ce16",
        2: "ce34bfbd-b3ed-4f62-b5d1-55b44d5e3060",
        3: "7f99176b-9e33-4898-8323-85a33b1c5959",
        4: "a03045e8-2a46-4863-8fc6-2227a2964027",
        5: "26171610-6251-41db-8112-a311bb32334b",
        6: "27199e59-2361-40f0-9f47-a5f63b336e84",
        7: "3bccc496-21d8-443f-8423-d69ec5131a43",
        8: "c7afeea0-1efa-406e-9a48-b1903d2a6108",
        9: "456a7533-92a3-405c-8ba4-c8543b69d800",
        10: "d8c4cf03-7c7b-46ad-8fbd-e0fb44942a59",
    },
}

# Gemini (model ids are configurable; confirm current ids in the Gemini docs).
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_TEXT_MODEL = env("GEMINI_TEXT_MODEL", default="gemini-3.1-flash-lite")
GEMINI_TTS_MODEL = env("GEMINI_TTS_MODEL", default="gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = env("GEMINI_TTS_VOICE", default="Algenib")
# Voices the app offers (male, female). An explicit request for any other voice is
# rejected, so a typo or abusive client can't trigger a paid TTS call with junk.
GEMINI_TTS_VOICES_ALLOWED = env.list(
    "GEMINI_TTS_VOICES_ALLOWED",
    default=["Algenib", "Sulafat"],
)
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
# Throttle counters live in Django's cache — see the CACHES section below, which
# uses a worker-shared cache in production so the limits stay accurate.
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

# --- Cache (backs DRF throttle counters) ------------------------------------
# DRF throttle counters live here. The default LocMemCache is PER-PROCESS, so
# with multiple gunicorn workers each keeps its own counter and the effective
# limit becomes rate × workers — i.e. the throttle leaks. To keep the limits
# accurate, production uses a cache shared across workers:
#   • REDIS_URL set  → Redis (use for a multi-host / load-balanced setup;
#                      requires `pip install redis`).
#   • else in prod   → file-based cache, shared across workers on one host with
#                      zero extra infrastructure (right for a single EC2 box).
#   • else (dev)     → LocMemCache (single process — perfectly fine locally).
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
elif IS_PRODUCTION:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(BASE_DIR / ".cache"),
        }
    }
# else: Django's built-in LocMemCache default (no CACHES block needed locally).

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
