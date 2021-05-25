from .settings import *

MIN_CALL_REQUEST_QUEUE_ITEMS = 0

# Tests fail if read-only connection is present:
if "dashboard" in DATABASES:
    DATABASES.pop("dashboard")
