import gzip
import json
from functools import cache
from pathlib import Path

import beeline
from google.cloud import storage


class StorageWriter:
    def write(self, path: str, data: object) -> None:
        ...


class LocalWriter(StorageWriter):
    prefix: str

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def write(self, path: str, data: object) -> None:
        local_path = Path(self.prefix, path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with local_path.open("w") as f:
            json.dump(data, f)


class DebugWriter(StorageWriter):
    prefix: str

    def __init__(self, prefix: str = ""):
        if not prefix.endswith("/"):
            prefix += "/"
        self.prefix = prefix

    def write(self, path: str, data: object) -> None:
        print(f"Would write to {self.prefix}{path}:")
        print(json.dumps(data, indent=4, sort_keys=True))
        print()


class GoogleStorageWriter(StorageWriter):
    bucket_name: str
    prefix: str

    def __init__(self, bucket_name: str, prefix: str = "") -> None:
        self.bucket_name = bucket_name
        self.prefix = prefix

    @cache
    @beeline.traced(name="core.exporter.storage.GoogleStorageWriter.get_bucket")
    def get_bucket(self) -> storage.Bucket:
        storage_client = storage.Client()
        return storage_client.bucket(self.bucket_name)

    @beeline.traced(name="core.exporter.storage.GoogleStorageWriter.write")
    def write(self, path: str, data: object) -> None:
        if self.prefix:
            path = self.prefix + "/" + path
        blob = self.get_bucket().blob(path)

        blob.cache_control = "public,max-age=120"
        blob.content_encoding = "gzip"
        blob.upload_from_string(
            gzip.compress(json.dumps(data).encode("ascii")),
            content_type="application/json",
            timeout=30,
        )
