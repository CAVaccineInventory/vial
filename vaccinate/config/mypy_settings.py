import os

# This file should only be loaded by Mypy; it sets default for
# environment variables which settings.py requires be set.  But
# because it is loaded as an extension, TYPE_CHECKING is not on; as
# such, use a hack to ensure that this is only loaded by mypy.
if "MYPY_CONFIG_FILE_DIR" not in os.environ:
    raise Exception(
        "mypy_settings.py should only be ever loaded by mypy, never at runtime!"
    )

os.environ["DJANGO_SECRET_KEY"] = "1"
os.environ["SOCIAL_AUTH_AUTH0_SECRET"] = "1"

from .settings import *
