"""ASGI config for the English reading DB browser."""
import os

from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "english_reading_browser.settings")

application = get_asgi_application()
