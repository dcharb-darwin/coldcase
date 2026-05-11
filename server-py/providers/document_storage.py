"""Document storage provider seam.

Cold Case never holds the document binary. We only resolve a `storage_uri` to
either a presigned URL the frontend can fetch directly, or — for the mock — a
local filesystem path used for dev only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


@dataclass
class StoredObject:
    storage_uri: str
    sha256: str
    size_bytes: int
    presigned_url: str | None = None


class DocumentStorageProvider(Protocol):
    name: str
    def head(self, storage_uri: str) -> StoredObject: ...
    def presign_get(self, storage_uri: str, *, ttl_seconds: int = 300) -> str: ...
    def resolve_path(self, storage_uri: str) -> str:
        """Return a local filesystem path the server process can open.

        Local provider returns the actual on-disk path; remote providers
        materialize to a temp file (or raise if not supported in MVP)."""
        ...


class LocalDocumentStorageProvider:
    """Dev provider. Treats `storage_uri` as a local filesystem path under
    `UPLOAD_DIRECTORY`. Hashes the file on `head` so callers can register
    a Document with a real sha256.
    """

    name = "local"

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.environ.get("UPLOAD_DIRECTORY", "./uploads")
        os.makedirs(self.base_dir, exist_ok=True)

    def resolve_path(self, storage_uri: str) -> str:
        if storage_uri.startswith("file://"):
            return storage_uri[len("file://"):]
        if os.path.isabs(storage_uri):
            return storage_uri
        return os.path.join(self.base_dir, storage_uri)

    def head(self, storage_uri: str) -> StoredObject:
        from lib.hash import hash_file
        path = self.resolve_path(storage_uri)
        if not os.path.exists(path):
            raise FileNotFoundError(f"document not found at {path}")
        sha, size = hash_file(path)
        return StoredObject(storage_uri=storage_uri, sha256=sha, size_bytes=size, presigned_url=None)

    def presign_get(self, storage_uri: str, *, ttl_seconds: int = 300) -> str:
        return f"local://{self.resolve_path(storage_uri)}"


class AzureBlobDocumentStorageProvider:
    """Real provider stub for agency Azure Blob storage.

    Real implementation uses azure-storage-blob + a tenant-owned account /
    container. Documents are never *uploaded* by Cold Case — they're already
    there from the agency's intake pipeline; we just register pointers.
    """

    name = "azure_blob"

    def head(self, storage_uri: str) -> StoredObject:
        raise NotImplementedError(
            "AzureBlobDocumentStorageProvider is not yet wired. "
            "Set PROVIDER_DOCUMENT_STORAGE=local for development."
        )

    def presign_get(self, storage_uri: str, *, ttl_seconds: int = 300) -> str:
        raise NotImplementedError

    def resolve_path(self, storage_uri: str) -> str:
        raise NotImplementedError(
            "Azure Blob inline text extraction requires materializing to a "
            "temp file — wire in Phase 2."
        )


def get_document_storage_provider() -> DocumentStorageProvider:
    choice = os.environ.get("PROVIDER_DOCUMENT_STORAGE", "local").lower()
    if choice == "local":
        return LocalDocumentStorageProvider()
    if choice in ("azure", "azure_blob"):
        return AzureBlobDocumentStorageProvider()
    raise ValueError(f"Unknown PROVIDER_DOCUMENT_STORAGE={choice!r}")
