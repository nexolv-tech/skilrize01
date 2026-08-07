import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Django Channels routing is layered on here in the phase that introduces
# realtime messaging; the ASGI entrypoint exists from Phase 0 so deployment
# topology never has to change.
application = get_asgi_application()
