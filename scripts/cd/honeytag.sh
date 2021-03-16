#!/usr/bin/env bash

# This is meant to be run from CloudBuild, not manually.

set -eu

SECRET_NAME="${SECRET_NAME:-honeycomb-marker-key}"

SECRET_VALUE=$(
	gcloud secrets versions access latest --secret="$SECRET_NAME" --format='get(payload.data)' |
		tr '_-' '/+' |
		base64 -d
)

DATASET="$1"
MARKERNAME="$2"
URL="$3"

# https://docs.honeycomb.io/api/markers/
curl "https://api.honeycomb.io/1/markers/$DATASET" \
	-X POST \
	-H "X-Honeycomb-Team: $SECRET_VALUE" \
	-d "{\"message\":\"$MARKERNAME\", \"type\":\"deploy\", \"url\":\"$URL\"}"
