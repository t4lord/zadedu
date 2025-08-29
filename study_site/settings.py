from pathlib import Path
import os, dj_database_url
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-_2rfpq5k=3lw#zx3x!v@3j#u#s0vlun9%bemt%_7tl(ub&t_m_'
DEBUG = True

ALLOWED_HOSTS = ["zadedu.onrender.com"]
CSRF_TRUSTED_ORIGINS = [
    "https://zadedu.onrender.com"
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'edu',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'study_site.middleware.BasicAuthMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'study_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # ← هنا نضيف مجلد القوالب
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'study_site.wsgi.application'


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    # إنتاج/Render: استخدم Postgres من Neon
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    # محلي: fallback إلى SQLite حتى لو ما فيه DATABASE_URL
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }



AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Riyadh'

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"   # هنا سيجمع collectstatic الملفات
# لو عندك مجلد ستايتك خاص بالمشروع (لأثناء التطوير)
STATICFILES_DIRS = [BASE_DIR / "static"]  # اتركه فقط إن كان المجلد موجودًا فعلاً
# (اختياري لكن مُستحسن للإنتاج)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
<<<<<<< HEAD
# احفظ اختيار الفصل لمدة سنة (بالثواني)
=======
>>>>>>> ea62e24 (feat: <وصف التعديل>)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_SAVE_EVERY_REQUEST = False
