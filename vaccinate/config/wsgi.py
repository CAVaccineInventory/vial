import os

from config.env import load_env
from django.core.wsgi import get_wsgi_application

load_env()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
