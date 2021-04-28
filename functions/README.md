# Build notifications

This creates a cloud function which is subscribed to the
`cloud-builds` topic, and sends build notifications for VIAL to a
Discord webhook.

It is built using Firebase, a wrapper around Google Cloud Functions.

## Deploy

```
firebase login
firebase deploy --only functions
```

To update the webhook URL:
```
firebase functions:config:set discord.build_hook=https://discord.com/...
```

## Provenance

Code based on [this
tutorial](https://codingcat.dev/tutorial/send-gcp-build-status-to-discord)
and its [repo](https://github.com/ajonp/gcp-build-discord-webhook),
with a bunch of changes to the content it sends.


## Pubsub messages

The data received from the pubsub is as follows:
```json
{
  "artifacts": {
    "images": [
      "us.gcr.io/django-vaccinateca/vaccinate:latest"
    ]
  },
  "availableSecrets": {
    "secretManager": [
      {
        "env": "_SENTRY_TOKEN",
        "versionName": "projects/373178984669/secrets/sentry-release-token/versions/latest"
      },
      {
        "env": "_SSH_KEY",
        "versionName": "projects/373178984669/secrets/github-deploy/versions/latest"
      }
    ]
  },
  "buildTriggerId": "d155ad70-3d3c-4c61-b3e4-39dd142d22d5",
  "createTime": "2021-04-28T17:22:26.740339083Z",
  "finishTime": "2021-04-28T17:25:35.558742Z",
  "id": "859e111f-a238-44f7-9e06-0fc09fe9ed8f",
  "images": [
    "us.gcr.io/django-vaccinateca/vaccinate:latest"
  ],
  "logUrl": "https://console.cloud.google.com/cloud-build/builds/859e111f-a238-44f7-9e06-0fc09fe9ed8f?project=373178984669",
  "logsBucket": "gs://373178984669.cloudbuild-logs.googleusercontent.com",
  "name": "projects/373178984669/locations/global/builds/859e111f-a238-44f7-9e06-0fc09fe9ed8f",
  "options": {
    "dynamicSubstitutions": true,
    "logging": "LEGACY",
    "substitutionOption": "ALLOW_LOOSE"
  },
  "projectId": "django-vaccinateca",
  "queueTtl": "3600s",
  "results": {
    "buildStepImages": [
      "sha256:a6b4bd99cfa22be16d039dbf6315884cc0f8330989f56afa66c28e91840bfd76",
      // ...
      "sha256:327d4a0a77ed8cbe3683263228c4f9dcb2896ec7947d015b7f81474b2fb08066"
    ],
    "buildStepOutputs": [
      "",
      // ...
      ""
    ],
    "images": [
      {
        "digest": "sha256:55db666e6e12fd5d098fd9e80d28493520f3de26f77c62385d144d956477322f",
        "name": "us.gcr.io/django-vaccinateca/vaccinate",
        "pushTiming": {
          "endTime": "2021-04-28T17:25:34.855442856Z",
          "startTime": "2021-04-28T17:25:33.563558814Z"
        }
      },
      {
        "digest": "sha256:55db666e6e12fd5d098fd9e80d28493520f3de26f77c62385d144d956477322f",
        "name": "us.gcr.io/django-vaccinateca/vaccinate:latest",
        "pushTiming": {
          "endTime": "2021-04-28T17:25:34.855442856Z",
          "startTime": "2021-04-28T17:25:33.563558814Z"
        }
      }
    ]
  },
  "source": {},
  "sourceProvenance": {},
  "startTime": "2021-04-28T17:22:27.320496022Z",
  "status": "SUCCESS",
  "steps": [
    {
      "args": [
        "-c",
        "echo \"$_SSH_KEY\" >> /root/.ssh/id_ed25519\nchmod 400 /root/.ssh/id_ed25519\ncp .github/known_hosts /root/.ssh/known_hosts\n"
      ],
      "entrypoint": "bash",
      "id": "set up SSH",
      "name": "gcr.io/cloud-builders/git",
      "pullTiming": {
        "endTime": "2021-04-28T17:22:34.912263148Z",
        "startTime": "2021-04-28T17:22:34.909801927Z"
      },
      "secretEnv": [
        "_SSH_KEY"
      ],
      "status": "SUCCESS",
      "timing": {
        "endTime": "2021-04-28T17:22:35.871781399Z",
        "startTime": "2021-04-28T17:22:34.909801927Z"
      },
      "volumes": [
        {
          "name": "ssh",
          "path": "/root/.ssh"
        }
      ]
    },
    // ...
    {
      "args": [
        "./scripts/cd/honeytag.sh",
        "vial-staging",
        "Deploy 7860c99",
        "https://github.com/CAVaccineInventory/vial/commits/7860c99ea90fb27d442701275149a4012c970fcb"
      ],
      "entrypoint": "bash",
      "id": "honeycomb tag",
      "name": "gcr.io/cloud-builders/gcloud",
      "pullTiming": {
        "endTime": "2021-04-28T17:25:30.022983040Z",
        "startTime": "2021-04-28T17:25:30.015514842Z"
      },
      "status": "SUCCESS",
      "timing": {
        "endTime": "2021-04-28T17:25:33.501715653Z",
        "startTime": "2021-04-28T17:25:30.015514842Z"
      }
    }
  ],
  "substitutions": {
    "BRANCH_NAME": "main",
    "COMMIT_SHA": "7860c99ea90fb27d442701275149a4012c970fcb",
    "REF_NAME": "main",
    "REPO_NAME": "vial",
    "REVISION_ID": "7860c99ea90fb27d442701275149a4012c970fcb",
    "SHORT_SHA": "7860c99",
    "TRIGGER_NAME": "staging",
    "_CLOUDSQL_INSTANCE": "django-vaccinateca:us-west2:staging",
    "_DB_INSTANCE_NAME": "staging",
    "_DEPLOY": "staging",
    "_DEPLOY_REGION": "us-west2",
    "_GCLOUD_SETTINGS_NAME": "django-staging-env",
    "_GCR_HOSTNAME": "us.gcr.io",
    "_IMAGE_NAME": "us.gcr.io/django-vaccinateca/vaccinate",
    "_SERVICE_NAME": "vaccinate"
  },
  "tags": [
    "trigger-d155ad70-3d3c-4c61-b3e4-39dd142d22d5"
  ],
  "timeout": "3600s",
  "timing": {
    "BUILD": {
      "endTime": "2021-04-28T17:25:33.563480959Z",
      "startTime": "2021-04-28T17:22:34.188603127Z"
    },
    "FETCHSOURCE": {
      "endTime": "2021-04-28T17:22:34.188512684Z",
      "startTime": "2021-04-28T17:22:28.204897795Z"
    },
    "PUSH": {
      "endTime": "2021-04-28T17:25:34.855488652Z",
      "startTime": "2021-04-28T17:25:33.563558186Z"
    }
  }
}
```
