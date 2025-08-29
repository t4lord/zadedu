import os
from pathlib import Path
import dj_database_url
BASE_DIR = Path(__file__).resolve().parent.parent

# لا تضع المفتاح الحقيقي هنا. على Render ضَع Environment Variable باسم SECRET_KEY
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key")

# DEBUG=1 للتطوير المحلي، و DEBUG=0 للإنتاج (Render)
DEBUG = os.environ.get("DEBUG", "0") == "1"

# يمكنك تمرير ALLOWED_HOSTS كسلسلة مفصولة بفواصل من المتغيرات البيئية
# مثال على Render: yourapp.onrender.com,example.com
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "edu",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise يجب أن يأتي مبكرًا بعد SecurityMiddleware
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
        "DIRS": [BASE_DIR / "templates"],  # ← مجلد القوالب المخصص
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

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# قاعدة البيانات: Postgres إذا وُجد DATABASE_URL، وإلا SQLite (بدون SSL)

USE_POOLER = os.getenv("USE_POOLER", "0") == "1"
CONN_MAX_AGE = 0 if USE_POOLER else 300  # مناسب مع نوم Neon

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,     # رابط Neon من البيئة
            conn_max_age=CONN_MAX_AGE,
            ssl_require=True,         # نفعّله فقط مع Postgres
        )
    }
    if os.getenv("DEBUG", "0") != "1":
        DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
DEFAULT_SUBJECTS = [
    "التفسير", "الحديث", "الفقه", "العقيدة", "النحو", "البلاغة", "التربية الإسلامية",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = True
USE_TZ = True

# ملفات الستاتيك
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"     # مكان جمع الملفات عند النشر (collectstatic)
# أبقه لو عندك مجلد static محلي تريد تضمينه
STATICFILES_DIRS = [BASE_DIR / "static"]

# تفعيل WhiteNoise مع ضغط ومانيفست (Django 5 يستخدم STORAGES بدل STATICFILES_STORAGE)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

# ملفات الميديا (للتحضير؛ محليًا فقط. على Render يُفضّل S3/Cloudinary)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# الجلسات كما وضعتها
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_SAVE_EVERY_REQUEST = False

# إعدادات الأمان (تفعل تلقائيًا عندما DEBUG=False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = (os.environ.get("SECURE_SSL_REDIRECT", "1") == "1") and not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30 if not DEBUG else 0  # 30 يوم في الإنتاج
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# CSRF الموثوقة: ضع دومين Render أو نطاقك عبر متغير بيئة واحد
# مثال قيمة: https://yourapp.onrender.com
CSRF_TRUSTED_ORIGINS = [
    os.environ.get("CSRF_ORIGIN", "https://example.com")
]

# لوجينغ بسيط إلى stdout لسهولة القراءة في Render Logs
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO" if not DEBUG else "DEBUG"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
