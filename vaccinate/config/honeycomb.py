import os

import beeline
import requests


def init():
    deploy = os.environ.get("DEPLOY", "unknown")
    if os.environ.get("HONEYCOMB_KEY"):
        beeline.init(
            writekey=os.environ.get("HONEYCOMB_KEY"),
            dataset=f"vial-{deploy}",
        )

        instance_id = "unknown"
        with beeline.tracer("metadata.id"):
            try:
                resp = requests.get(
                    "http://metadata.google.internal/computeMetadata/v1/instance/id",
                    headers={
                        "Metadata-Flavor": "Google",
                    },
                    timeout=1,
                )
                beeline.add_field("response.status", resp.status_code)
                beeline.add_field("response.content", resp.content)
                instance_id = resp.content.decode("utf-8")
                beeline.add_field("meta.instance_id", instance_id)
            except Exception:
                beeline.add_field("response.status", 599)

        def add_instance_id(event):
            event["meta.instance_id"] = instance_id

        beeline.close()
        beeline.init(
            writekey=os.environ.get("HONEYCOMB_KEY"),
            dataset=f"vial-{deploy}",
            presend_hook=add_instance_id,
        )
