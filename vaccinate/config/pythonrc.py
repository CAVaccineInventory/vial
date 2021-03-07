"""
Loaded by `./manage shell`, this makes all of the models readily
available.

isort:skip_file
"""
try:
    from django.conf import settings  # noqa: F401

    from django.contrib.auth.models import *  # noqa: F401, F403
    from api.models import *  # noqa: F401, F403
    from core.models import *  # noqa: F401, F403
except Exception:
    import traceback

    print("\nException importing core modules on startup!")
    traceback.print_exc()
else:
    print("\nSuccessfully imported models and settings.")
