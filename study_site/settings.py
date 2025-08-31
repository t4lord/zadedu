# study_site/settings.py
import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# =========[ 1) بيئة التشغيل ]=========
DJANGO_ENV = os.getenv("DJANGO_ENV", "development").lower()  # 'development' | 'production' | 'test'
DEBUG = os.getenv("DEBUG", "1" if DJANGO_ENV == "development" else "0") == "1"
IS_PROD = (DJANGO_ENV == "production") and not DEBUG

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key")

# =========[ 2) Hosts & CSRF ]=========
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*" if not IS_PROD else "").split(",") if h.strip()]
# في الإنتاج اضبط هذا المتغير مثل: ALLOWED_HOSTS=zadedu.onrender.com
CSRF_TRUSTED_ORIGINS = [
    # يجب أن يتضمن البروتوكول
    os.environ.get("CSRF_ORIGIN", "http://127.0.0.1:8000" if not IS_PROD else "https://zadedu.onrender.com")
]

# =========[ 3) التطبيقات ]=========
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "edu",
]

# =========[ 4) Middleware ]=========
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise للإنتاج فقط عادة، لكن لا بأس بوجوده دائمًا
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "study_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "study_site.wsgi.application"

# =========[ 5) قاعدة البيانات ]=========
DEFAULT_SQLITE_URL = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

USE_POOLER = os.getenv("USE_POOLER", "0") == "1"   # لـ Neon pooler لاحقًا
CONN_MAX_AGE = 0 if USE_POOLER else (300 if IS_PROD else 0)

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=CONN_MAX_AGE,
            ssl_require=True,          # عند Postgres
        )
    }
else:
    # محليًا: SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# صحّة الاتصال للإنتاج فقط
if IS_PROD:
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# =========[ 6) الضبط العام ]=========
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========[ 7) Static & Media ]=========
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# =========[ 8) الجلسات ]=========
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_SAVE_EVERY_REQUEST = False

# =========[ 9) الأمان ]=========
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # للمنصات مثل Render
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1" if IS_PROD else "0") == "1"

SESSION_COOKIE_SECURE = IS_PROD
CSRF_COOKIE_SECURE = IS_PROD

SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "2592000" if IS_PROD else "0"))  # 30 يومًا
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PROD
SECURE_HSTS_PRELOAD = IS_PROD

# =========[ 10) كلمات المرور ]=========
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========[ 11) بيانات أولية مخصصة ]=========
DEFAULT_SUBJECTS = [
    "التفسير", "الحديث", "الفقه", "العقيدة", "اللغة العربية", "التربية الإسلامية", "السيرة"
]
