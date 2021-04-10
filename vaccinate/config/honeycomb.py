import os

import beeline


def init():
    deploy = os.environ.get("DEPLOY", "unknown")
    if os.environ.get("HONEYCOMB_KEY"):
        beeline.init(
            writekey=os.environ.get("HONEYCOMB_KEY"),
            dataset=f"vial-{deploy}",
        )
