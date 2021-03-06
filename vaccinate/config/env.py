import io
import os

from dotenv import load_dotenv


def load_env():
    if "GCLOUD_SETTINGS_NAME" in os.environ:
        # Only import these if necessary
        import google.auth
        from google.cloud import secretmanager

        _, project = google.auth.default()

        if project:
            client = secretmanager.SecretManagerServiceClient()
            settings_name = os.environ["GCLOUD_SETTINGS_NAME"]
            name = f"projects/{project}/secrets/{settings_name}/versions/latest"
            payload = client.access_secret_version(name=name).payload.data.decode(
                "UTF-8"
            )
            load_dotenv(stream=io.StringIO(payload))
    else:
        load_dotenv()
