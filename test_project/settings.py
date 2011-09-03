# Django settings for demo project.

DEBUG = True
TEMPLATE_DEBUG = DEBUG

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/tmp/db.sqlite',       # Or path to database file if using sqlite3.
        'USER': '',                     # Not used with sqlite3.
        'PASSWORD': '',                 # Not used with sqlite3.
        'HOST': '',                     # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                     # Set to empty string for default. Not used with sqlite3.
    }
}


# Make this unique, and don't share it with anybody.
SECRET_KEY = '))&_fn7otvb(o(t$1#dt+&0$drsyo%h+h-*7#5bo*1y5-zmlob'

ROOT_URLCONF = 'test_project.urls'

INSTALLED_APPS = (
    'test_project.sample_app',
)


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': '127.0.0.1:11211',
    },
    'other': {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': '127.0.0.1:11212',
    }
}
