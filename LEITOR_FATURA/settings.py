# Bibliotecas padrão python
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega as variáveis do arquivo .env na raiz do projeto
load_dotenv(BASE_DIR / '.env')


def env(name, default=None):
    return os.getenv(name, default)


def env_bool(name, default=False):
    return str(env(name, default)).lower() == 'true'


def env_list(name, default=''):
    return [item.strip() for item in env(name, default).split(',') if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', 'django-insecure-h_*m42&o=gyt_t(wujyv5gm=howo)lyyr-$lo-z+q=k602!in(')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DEBUG', False)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', '*')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', 'https://alpsistemas.up.railway.app')


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # My apps   
    'app.core',
    'app.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'LEITOR_FATURA.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],  # Directory for custom templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'LEITOR_FATURA.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

database_url = (
    env('DATABASE_URL')
    or env('RAILWAY_DATABASE_URL')
    or env('DATABASE_PUBLIC_URL')
    or env('POSTGRES_URL')
)
if database_url:
    url = urlparse(database_url)
    if url.scheme.startswith('postgres'):
        query_options = parse_qs(url.query)
        options = {}
        if 'sslmode' in query_options:
            options['sslmode'] = query_options['sslmode'][0]

        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path.lstrip('/') or '',
            'USER': url.username or '',
            'PASSWORD': url.password or '',
            'HOST': url.hostname or '',
            'PORT': str(url.port or ''),
        }
        if options:
            DATABASES['default']['OPTIONS'] = options
else:
    db_name = env('POSTGRES_DB') or env('PGDATABASE')
    db_user = env('POSTGRES_USER') or env('PGUSER')
    db_password = env('POSTGRES_PASSWORD') or env('PGPASSWORD')
    db_host = env('POSTGRES_HOST') or env('PGHOST')
    db_port = env('POSTGRES_PORT') or env('PGPORT')

    if db_name:
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': db_name,
            'USER': db_user or '',
            'PASSWORD': db_password or '',
            'HOST': db_host or 'localhost',
            'PORT': db_port or '5432',
        }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = False

USE_L10N = True # serve para deixar o formato da data em 'd/m/Y'

LANGUAGE_CODE='pt-br'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email configuration
EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(env('EMAIL_PORT', 587))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', 'alpsistemascg@gmail.com')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
CONTACT_EMAIL = env('CONTACT_EMAIL', 'alpsistemascg@gmail.com')
WHATSAPP_NUMBER = env('WHATSAPP_NUMBER', '')

# Jazzmin (Admin theme) settings
JAZZMIN_SETTINGS = {
    "site_title": "ALP SISTEMAS",
    "site_header": "ALP SISTEMAS",
    "welcome_sign": "Bem-vindo ao painel administrativo",
    "topmenu_links": [
        {"name": "Início", "url": "core:index"},
    ],
}
