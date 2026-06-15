"""
Django settings for config project (FitCoach).

Configuration pilotée par variables d'environnement (python-dotenv).
Voir .env.example pour la liste des variables attendues.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Charge le fichier .env situé à la racine du projet (si présent).
load_dotenv(BASE_DIR / ".env")

# Vrai pendant l'exécution de la suite de tests (`manage.py test`).
# Sert à neutraliser les dépendances externes (Redis) sans config éphémère.
RUNNING_TESTS = "test" in sys.argv


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-production",
)

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]


# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # requis par allauth
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
]

LOCAL_APPS = [
    "accounts",
    "nutrition",
    "training",
    "tracking",
    "coach",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise sert les fichiers statiques sans nginx dédié (juste après Security).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # allauth : gère les requêtes liées au compte (doit suivre AuthenticationMiddleware).
    "allauth.account.middleware.AccountMiddleware",
    # Onboarding obligatoire : renvoie vers le formulaire tant que le profil
    # n'est pas créé (doit suivre l'authentification pour connaître l'utilisateur).
    "accounts.middleware.OnboardingRequiredMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"


# Database — PostgreSQL
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

USE_POSTGRES = env_bool("DJANGO_USE_POSTGRES", False)

POSTGRES_DB = os.environ.get("POSTGRES_DB") or os.environ.get("DB_NAME", "fitcoach")
POSTGRES_USER = os.environ.get("POSTGRES_USER") or os.environ.get("DB_USER", "fitcoach")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("DB_PASSWORD", "fitcoach")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST") or os.environ.get("DB_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT") or os.environ.get("DB_PORT", "5432")

# En prod, DATABASE_URL (ex: postgres://user:pass@db:5432/fitcoach) a priorité.
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600),
    }
elif USE_POSTGRES or POSTGRES_HOST in {"db", "postgres"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": POSTGRES_DB,
            "USER": POSTGRES_USER,
            "PASSWORD": POSTGRES_PASSWORD,
            "HOST": POSTGRES_HOST,
            "PORT": POSTGRES_PORT,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Cache & sessions — Redis
# https://docs.djangoproject.com/en/6.0/topics/cache/#redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
USE_REDIS = env_bool("DJANGO_USE_REDIS", False)

# Redis désactivé d'office pendant les tests : la suite tourne sur un cache
# local et des sessions en base, sans dépendre d'un Redis démarré.
if USE_REDIS and not RUNNING_TESTS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "fitcoach-local",
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"


# Modèle utilisateur personnalisé (app accounts)
AUTH_USER_MODEL = "accounts.User"

# Authentification — django-allauth (multi-utilisateurs, Phase 3)
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    # Backend Django par défaut (login admin, etc.).
    "django.contrib.auth.backends.ModelBackend",
    # Backend allauth (login par e-mail).
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "account_login"
# Après connexion / inscription : tableau de bord, qui redirige vers
# l'onboarding tant que l'utilisateur n'a pas de profil.
LOGIN_REDIRECT_URL = "tracking:dashboard"
LOGOUT_REDIRECT_URL = "account_login"

# Configuration allauth : inscription e-mail + mot de passe, réinitialisation.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # pas de SMTP en dev ; activable en prod
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGOUT_ON_GET = False  # déconnexion via POST (CSRF)
# En dev, les e-mails (reset password) s'affichent dans la console.
if not env_bool("DJANGO_USE_SMTP", False):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@fitcoach.infotechno.eu")


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization — interface en français (Belgique)
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "fr"

TIME_ZONE = "Europe/Brussels"

USE_I18N = True

USE_TZ = True


# Static & media files
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise : en prod, fichiers statiques compressés + hashés (cache-busting).
# En dev (DEBUG), on garde le stockage par défaut pour que runserver les serve
# sans avoir à lancer collectstatic.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Intégration API Anthropic (app coach) — ne jamais commiter la clé
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


# Sécurité — production derrière reverse proxy (nginx) qui termine le HTTPS.
# https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/
#
# Les bascules de sécurité sont activées par défaut quand DEBUG=False, et
# peuvent être surchargées individuellement par variable d'environnement.

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# Le proxy transmet le protocole d'origine via X-Forwarded-Proto : Django sait
# ainsi que la requête est bien en HTTPS même si le conteneur reçoit du HTTP.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Redirige tout le trafic HTTP vers HTTPS (le proxy gère le certificat).
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)

# Cookies de session / CSRF uniquement transmis en HTTPS.
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)

# HSTS : force le navigateur à n'utiliser que HTTPS (0 = désactivé en dev).
# 31536000 = 1 an. Activez include_subdomains/preload une fois le HTTPS stable.
SECURE_HSTS_SECONDS = int(
    os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", not DEBUG)
