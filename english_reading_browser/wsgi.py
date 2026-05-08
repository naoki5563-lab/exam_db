"""WSGI config for the English reading DB browser."""
import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "english_reading_browser.settings")

application = get_wsgi_application()
