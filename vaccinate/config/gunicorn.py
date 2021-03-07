import os

import beeline


# Honeycomb's beeline has to be initialized _after_ the fork:
# https://docs.honeycomb.io/getting-data-in/python/beeline/#gunicorn
def post_worker_init(worker):
    deploy = os.environ.get("DEPLOY", "unknown")
    beeline.init(
        writekey=os.environ.get("HONEYCOMB_KEY"),
        dataset=f"vial-{deploy}",
    )
