import json
import os

from config import honeycomb
from django.apps import AppConfig as BaseAppConfig


class AppConfig(BaseAppConfig):
    name = "core"
    verbose_name = "VIAL core"

    def ready(self):
        if "gunicorn" in os.environ.get("SERVER_SOFTWARE", ""):
            # This is a perforking server; we need to do this setup in
            # the children.
            return
        honeycomb.init()
