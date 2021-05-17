import gzip
import json
from functools import cache
from pathlib import Path
from typing import Iterator

import beeline
from google.cloud import (  # type: ignore  # XXX: This works when mypy is re-run with a cache?
    storage,
)


class StorageWriter:
    def write(self, path: str, content_stream: Iterator[str]) -> None:
        ...


class LocalWriter(StorageWriter):
    prefix: str

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def write(self, path: str, content_stream: Iterator[str]) -> None:
        local_path = Path(self.prefix, path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with local_path.open("w") as f:
            for chunk in content_stream:
                f.write(chunk)


class DebugWriter(StorageWriter):
    prefix: str

    def __init__(self, prefix: str = ""):
        if not prefix.endswith("/"):
            prefix += "/"
        self.prefix = prefix

    def write(self, path: str, content_stream: Iterator[str]) -> None:
        data = json.loads("".join(content_stream))
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
    def write(self, path: str, content_stream: Iterator[str]) -> None:
        if self.prefix:
            path = self.prefix + "/" + path
        blob = self.get_bucket().blob(path)

        blob.cache_control = "public,max-age=120"
        blob.content_encoding = "gzip"
        with blob.open("wb") as f:
            with gzip.open(f, "w") as gzip_f:
                for chunk in content_stream:
                    gzip_f.write(chunk.encode("ascii"))
