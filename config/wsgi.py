"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
from django.core.wsgi import get_wsgi_application

# Expose settings for WSGI servers (e.g., Gunicorn).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# WSGI application callable used by the server.
application = get_wsgi_application()
