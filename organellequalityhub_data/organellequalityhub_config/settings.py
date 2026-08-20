from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False") == "True"

RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

ALLOWED_HOSTS = []
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
if os.getenv("DJANGO_ALLOWED_HOSTS"):
    ALLOWED_HOSTS += os.getenv("DJANGO_ALLOWED_HOSTS").split(",")

CSRF_TRUSTED_ORIGINS = []
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Render forwards requests over plain HTTP internally and tells us the
# real scheme through this header, so this is how Django knows a
# request was actually HTTPS.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Separate from the block above so it can be turned off for a local,
# plain-HTTP test run without touching every other production setting.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", str(not DEBUG)) == "True"

# Application definition

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.guardian",
    "unfold.contrib.simple_history",
    "unfold.contrib.location_field",
    "unfold.contrib.constance",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "search_function",
    "plastid_interaction",
    "genome_map",
    "organism_metadata",
    "organelle_file_generator",
    "django_pandas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "organellequalityhub_config.urls"

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

WSGI_APPLICATION = "organellequalityhub_config.wsgi.application"

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
    "supabase": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "postgres"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    },
}

DATABASE_ROUTERS = ["organellequalityhub_config.routers.SupabaseRouter"]


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

UNFOLD = {
    "SITE_HEADER": "Plastid IR Admin",
    "SITE_TITLE": "Plastid IR Admin",
    "COLORS": {
        "primary": {
            "50": "236 250 234",
            "100": "218 245 214",
            "200": "181 236 172",
            "300": "144 226 131",
            "400": "118 219 102",
            "500": "97 214 79",
            "600": "67 198 47",
            "700": "53 157 37",
            "800": "39 116 27",
            "900": "28 83 19",
            "950": "18 54 13",
        },
        "base": {
            "50": "236 242 236",
            "100": "214 228 214",
            "200": "173 201 173",
            "300": "132 174 132",
            "400": "94 140 94",
            "500": "64 106 64",
            "600": "45 77 45",
            "700": "33 56 33",
            "800": "23 40 23",
            "900": "15 27 15",
            "950": "8 15 8",
        },
    },
}

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Only use WhiteNoise's hashed static files in production. Locally,
# runserver serves files straight from static/ and doesn't understand
# the hashed filenames, so it would break local testing.
if not DEBUG:
    STORAGES["staticfiles"][
        "BACKEND"
    ] = "whitenoise.storage.CompressedManifestStaticFilesStorage"
GENBANK_DIR = os.path.join(BASE_DIR, "plastid_interaction", "plastid_files")

# Root directory containing plastid_files/ and mitochondrial_files/.
# Resolution order: GENBANK_ROOT in .env -> parent of BASE_DIR (if the data
# folders already live there) -> BASE_DIR as a last resort.
_GENBANK_PARENT = BASE_DIR.parent
if os.getenv("GENBANK_ROOT"):
    GENBANK_ROOT = os.getenv("GENBANK_ROOT")
elif (_GENBANK_PARENT / "plastid_files").is_dir() or (
    _GENBANK_PARENT / "mitochondrial_files"
).is_dir():
    GENBANK_ROOT = _GENBANK_PARENT
else:
    GENBANK_ROOT = BASE_DIR

# Supabase Storage — used by genome_upload management command
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
