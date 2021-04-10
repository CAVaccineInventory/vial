import contextlib
from typing import Any

import beeline
from beeline.middleware.django import HoneyDBWrapper
from django.core.management.base import BaseCommand
from django.db import connections


class BeelineCommand(BaseCommand):
    def execute(self, *args: Any, **options: Any) -> str:
        try:
            db_wrapper = HoneyDBWrapper()
            # db instrumentation is only present in Django > 2.0
            with contextlib.ExitStack() as stack:
                for connection in connections.all():
                    stack.enter_context(connection.execute_wrapper(db_wrapper))
                with beeline.tracer(name=self.__class__.__module__):
                    output = super().execute(*args, **options)
        finally:
            beeline.close()
        return output
