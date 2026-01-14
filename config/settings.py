from pathlib import Path
import os
from datetime import timedelta  # Добавляем импорт для timedelta
from decouple import config as decouple_config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = decouple_config('SECRET_KEY', default='django-insecure-i0kjc4brza@^6%9(e_a^c-fp=lv8#iuca3bw@^k&$#6*%!h$m-')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = decouple_config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = decouple_config('ALLOWED_HOSTS', default='*', cast=Csv())

AUTH_USER_MODEL = 'profile.User'
LOGIN_URL = '/'



CSRF_TRUSTED_ORIGINS = decouple_config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:5173,http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000',
    cast=Csv()
)

CORS_ALLOW_CREDENTIALS = True 

# CORS settings
# pip install django-cors-headers
CORS_ALLOWED_ORIGINS = decouple_config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173',
    cast=Csv()
)


CORS_ALLOW_CREDENTIALS = True  # Must be True to allow cookies with requests
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'Authorization',
    'Content-Type',
    'X-CSRFToken',
    'X-Requested-With',
]

INSTALLED_APPS = [
    "unfold", 
    "unfold.contrib.filters",
    "unfold.contrib.forms", 
    'django.contrib.admin',
    'django_json_widget',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'rest_framework.authtoken',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django_extensions',
    'multiselectfield',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'profile.apps.ProfileConfig',
    'signals.apps.SignalsConfig',
    'frontend_api.apps.FrontendApiConfig',
    'graphql_app.apps.GraphQLConfig',
    'notifications.apps.NotificationsConfig',
    'client_api.apps.ClientApiConfig',
    'django_crontab',
]



REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.CustomPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    # Throttling применяется только для client_api через ClientAPIView
    # Для всех остальных API (frontend_api, graphql и т.д.) ограничений нет
}

# Лимиты запросов для Client API
CLIENT_API_DAILY_RATE_LIMIT = decouple_config('CLIENT_API_DAILY_RATE_LIMIT', default=500, cast=int)  # 500 запросов в сутки для оплаченных аккаунтов
FREE_CLIENT_LIMIT = decouple_config('FREE_CLIENT_LIMIT', default=100, cast=int)  # 100 запросов всего (не дневное) для бесплатных аккаунтов


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'client_api.middleware.ClientAPIExceptionMiddleware',  # Client API JSON error handling
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Добавляем общую директорию шаблонов
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database settings
DATABASES = {
    'default': {
        'ENGINE': decouple_config('DATABASE_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': decouple_config('DATABASE_NAME', default=os.path.join(BASE_DIR, 'db.sqlite3')),
        'USER': decouple_config('DATABASE_USER', default=''),
        'PASSWORD': decouple_config('DATABASE_PASSWORD', default=''),
        'HOST': decouple_config('DATABASE_HOST', default=''),
        'PORT': decouple_config('DATABASE_PORT', default=''),
    }
}

# Password validation settings
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

# Internationalization settings
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Media and static files settings
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Базовый URL для изображений
BASE_IMAGE_URL = decouple_config('BASE_IMAGE_URL', default='http://127.0.0.1:8000/')

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'assets')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

FIRST_DAY_OF_WEEK = 1

# Twitter API settings
TW_API_URL = decouple_config('TW_API_URL', default='https://twapi.dimden.dev')
TW_API_TOKEN = decouple_config('TW_API_TOKEN', default='')
PINATA_TOKEN = decouple_config('PINATA_TOKEN', default='')
PINATA_API_URL = decouple_config('PINATA_API_URL', default='https://api.pinata.cloud/v3/farcaster')

# Mailgun settings for production email sending
MAILGUN_API_KEY = decouple_config('MAILGUN_API_KEY', default='')
MAILGUN_DOMAIN = decouple_config('MAILGUN_DOMAIN', default='mail.theveck.com')

OPENAI_API_KEY = decouple_config('OPENAI_API_KEY', default='')


UNFOLD = {
   "SITE_TITLE": "VECK",
   "SITE_HEADER": "VECK",
   "SITE_URL": "/",
   
   "COLORS": {
        "primary": {
            "50": "#404040",
            "100": "#262626",
            "200": "#171717",
            "300": "#0a0a0a",
            "400": "#000000",
            "500": "#000000",
            "600": "#000000",
            "700": "#000000",
            "800": "#000000",
            "900": "#000000"
        },
        "secondary": {
            "50": "#f8fafc",
            "100": "#f1f5f9",
            "200": "#e2e8f0"
        }
    },
   "SIDEBAR": {
       "show_search": True,
       "show_all_applications": True,
       "navigation_collapsed": False,
       "categories": [
           {
               "name": "User Management",
               "models": ["profile.*"],
               "icon": "users"
           },
           {
               "name": "Signals",
               "models": ["signals.*"],
               "icon": "bolt"
           }
       ]
   },

   "EXTENSIONS": {
       "modeltranslation": {
           "languages": ["en", "ru"],
           "flags": {
               "en": "🇬🇧",
               "ru": "🇷🇺"
           },
           "default": "en"
       }
   },

   "APPEARANCE": {
       "brand_color": "blue",
       "theme": "system",
       "buttons_uppercase": False,
   },

   "DASHBOARD": {
       "show_recent_actions": True,
       "show_quick_actions": True,
       "enable_breadcrumbs": True,
   },

   "CSS_CLASSES": {
       "container": "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8",
       "sidebar": "2xl:w-72 bg-white dark:bg-gray-800",
       "content": "py-8",
       "card": "shadow-sm rounded-lg",
       "table": "min-w-full divide-y divide-gray-200",
   },

   "TABLES": {
       "sticky_header": True,
       "row_hover": True,
       "row_selection": True,
   },

   "FEATURES": {
       "search_in_sidebar": True,
       "navigation_collapse": True,
       "fixed_sidebar": True,
       "show_model_counts": True,
       "show_breadcrumbs": True,
       "search_all_models": True,
       "actions_sticky": True
   }
}

# Настройки Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # Срок действия access токена
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),     # Срок действия refresh токена
    'AUTH_HEADER_TYPES': ('Bearer',),                # Проверьте, что здесь указан Bearer
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',        # Имя заголовка
    'USER_ID_FIELD': 'id',                          # Поле с ID пользователя
    'USER_ID_CLAIM': 'user_id',                     # Название поля в JWT
}

# Настройки для django-crontab
CRONJOBS = [
    ('*/15 * * * *', 'django.core.management.call_command', ['send_digest'], {'verbosity': 1}),
    # On the 1st day of each month at 02:15 UTC: recalculate monthly signals counters
    ('15 2 1 * *', 'django.core.management.call_command', ['update_monthly_signals_count'], {'verbosity': 1}),
    # Every 3 days at 04:45 UTC: refresh participant web2/web3 flags
    ('45 4 */3 * *', 'django.core.management.call_command', ['update_participant_web3_flags'], {'verbosity': 1}),
]

# Логирование для cron задач
CRONTAB_COMMAND_SUFFIX = '2>&1'