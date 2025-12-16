# Bibliotecas padrão python
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega as variáveis do arquivo .env na raiz do projeto
load_dotenv(dotenv_path=str(BASE_DIR / '.env'))


def env(name, default=None):
    return os.getenv(name, default)


def env_bool(name, default=False):
    value = env(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 't', 'yes', 'y', 'on'}


def env_list(name, default=''):
    return [item.strip() for item in env(name, default).split(',') if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', 'django-insecure-h_*m42&o=gyt_t(wujyv5gm=howo)lyyr-$lo-z+q=k602!in(')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DEBUG', True)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')
if not ALLOWED_HOSTS:
    # Em produção, permita domínios do Railway; em desenvolvimento mantenha * para evitar erro por host.
    ALLOWED_HOSTS = ['alpfaturas.up.railway.app', 'localhost', '127.0.0.1']
    if DEBUG:
        ALLOWED_HOSTS.append('*')

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', 'https://alpfaturas.up.railway.app')


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
    'app.core.middleware.InactiveLogoutMiddleware',
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

DATABASE_URL = (
    env("DATABASE_URL")
    or env("RAILWAY_DATABASE_URL")
    or env("POSTGRES_URL")
)
FORCE_SQLITE = env_bool("USE_SQLITE", False)

# Permite usar SQLite (padrão) se nenhuma URL estiver definida ou se forçarmos via env.
if FORCE_SQLITE or not DATABASE_URL:
    sqlite_name = env('SQLITE_NAME', 'db.sqlite3')
    sqlite_path = Path(sqlite_name)
    if not sqlite_path.is_absolute():
        sqlite_path = BASE_DIR / sqlite_path

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
        }
    }
else:
    url = urlparse(DATABASE_URL)

    # Extração de parâmetros opcionais (?sslmode=require, etc.)
    query_options = parse_qs(url.query)
    options = {}
    if 'sslmode' in query_options:
        options['sslmode'] = query_options['sslmode'][0]

    if url.scheme.startswith('sqlite'):
        db_path = url.path or ''
        if db_path in {'', '/'}:
            db_path = BASE_DIR / 'db.sqlite3'
        else:
            db_path = Path(db_path.lstrip('/'))
            if not db_path.is_absolute():
                db_path = BASE_DIR / db_path

        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': db_path,
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': url.path.lstrip('/'),
                'USER': url.username,
                'PASSWORD': url.password,
                'HOST': url.hostname,
                'PORT': url.port,
            }
        }

        if options:
            DATABASES['default']['OPTIONS'] = options


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

USE_TZ = True

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
if not DEBUG:
    # Evita erro 500 caso o manifest dos estáticos não exista (deploys sem collectstatic).
    WHITENOISE_MANIFEST_STRICT = False

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email configuration
EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(env('EMAIL_PORT', 587))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', 'andreportol@gmail.com')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '').replace(' ', '')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
CONTACT_EMAIL = env('CONTACT_EMAIL', 'alpsistemascg@gmail.com')
WHATSAPP_NUMBER = env('WHATSAPP_NUMBER', '')
PIX_KEY = env('PIX_KEY', 'alpsistemascg@gmail.com')
# Tempo de sessão: 15 minutos (renova a cada requisição)
SESSION_IDLE_TIMEOUT = 15 * 60
SESSION_COOKIE_AGE = SESSION_IDLE_TIMEOUT
SESSION_SAVE_EVERY_REQUEST = True

# Jazzmin (Admin theme) settings
JAZZMIN_SETTINGS = {
    "site_title": "ALP SISTEMAS",
    "site_header": "ALP SISTEMAS",
    "welcome_sign": "Bem-vindo ao painel administrativo",
    "site_brand": "ALP SISTEMAS",
    "site_logo": "img/logomarca.png",
    "login_logo": "img/logomarca.png",
    "custom_css": "css/admin_custom.css",
    "topmenu_links": [
        {"name": "Início", "url": "core:index"},
    ],
}
