import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-dev-key-change-in-production-abc123xyz'
)

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1'
).split(',')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',

    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',

    'ingestion',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    'whitenoise.middleware.WhiteNoiseMiddleware',

    'corsheaders.middleware.CorsMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',

    'django.middleware.common.CommonMiddleware',

    'django.middleware.csrf.CsrfViewMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',

    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'core.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],

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


WSGI_APPLICATION = 'core.wsgi.application'


DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{BASE_DIR / "db.sqlite3"}'
)

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
        'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
    },

    {
        'NAME':
        'django.contrib.auth.password_validation.MinimumLengthValidator'
    },

    {
        'NAME':
        'django.contrib.auth.password_validation.CommonPasswordValidator'
    },

    {
        'NAME':
        'django.contrib.auth.password_validation.NumericPasswordValidator'
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = (
    'whitenoise.storage.CompressedManifestStaticFilesStorage'
)


MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


MAX_UPLOAD_SIZE = 10 * 1024 * 1024


REST_FRAMEWORK = {

    'DEFAULT_AUTHENTICATION_CLASSES': [

        'rest_framework.authentication.SessionAuthentication',

        'rest_framework.authentication.BasicAuthentication',

    ],

    'DEFAULT_PERMISSION_CLASSES': [

        'rest_framework.permissions.IsAuthenticated',

    ],

    'DEFAULT_PAGINATION_CLASS':
        'rest_framework.pagination.PageNumberPagination',

    'PAGE_SIZE': 50,
}


# ----------------------------
# CORS
# ----------------------------

CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://localhost:3000'
).split(',')

CORS_ALLOW_ALL_ORIGINS = os.environ.get(
    'CORS_ALLOW_ALL_ORIGINS',
    'False'
) == 'True'

CORS_ALLOW_CREDENTIALS = True


# ----------------------------
# CSRF
# ----------------------------

CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173'
).split(',')


# Required for frontend/backend on different domains

CSRF_COOKIE_SECURE = True

SESSION_COOKIE_SECURE = True

CSRF_COOKIE_SAMESITE = "None"

SESSION_COOKIE_SAMESITE = "None"


# Optional but useful

CSRF_COOKIE_HTTPONLY = False