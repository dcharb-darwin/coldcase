"""Artifact storage seam.

All Cold Case-generated PDFs (signed report, chain-of-custody, case
manifest, diff) and ZIPs (discovery package) flow through this seam.
Today: local-disk via `LocalArtifactStore`. Phase B: customer-side
Azure Blob / S3 / SharePoint adapters that swap in via the
`COLDCASE_ARTIFACT_STORE` env var — no call-site changes needed.

The seam is intentionally small: `put`, `exists`, `get_local_path`,
`presigned_get_url`. Each export service produces bytes and calls `put`
once; downstream readers call `get_local_path` (for FastAPI's
FileResponse, which streams off-disk efficiently) or
`presigned_get_url` (for clients that should fetch the bytes from
customer storage directly).

Note: the signed-report PDF and the chain-of-custody PDF are immutable
once written (the signature pins the content). The artifact store
treats `put` as idempotent — re-writing the same bytes under the same
key is a no-op.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol


logger = logging.getLogger(__name__)


@dataclass
class StoredArtifact:
    key: str                # e.g. "reports/<id>.pdf" or "discovery/<case>-<ts>.zip"
    uri: str                # provider-specific (file://, azure://, s3://)
    size_bytes: int
    content_type: str


class ArtifactStore(Protocol):
    name: str

    def put(self, key: str, data: bytes, *, content_type: str) -> StoredArtifact: ...
    def exists(self, key: str) -> bool: ...
    def get_local_path(self, key: str) -> str:
        """Return a local filesystem path the FastAPI process can open.
        Local provider returns the actual on-disk path; remote providers
        download to a temp file (deleted by the OS on next reboot). Raises
        FileNotFoundError if the key doesn't exist in the store."""
        ...
    def presigned_get_url(self, key: str, *, ttl_seconds: int = 300) -> str: ...


class LocalArtifactStore:
    """Default. Writes to UPLOAD_DIRECTORY. Keys map directly to subpaths
    so existing call sites that already know e.g. `reports/<id>.pdf`
    continue to work without translation."""

    name = "local"

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.environ.get("UPLOAD_DIRECTORY", "./uploads")

    def _path(self, key: str) -> str:
        # Defense against directory traversal: keys with .. are rejected.
        if ".." in key.split("/"):
            raise ValueError(f"invalid key contains '..': {key!r}")
        return os.path.join(self.base_dir, key)

    def put(self, key: str, data: bytes, *, content_type: str) -> StoredArtifact:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Idempotent: if the bytes haven't changed, don't bother rewriting.
        if os.path.exists(path) and os.path.getsize(path) == len(data):
            with open(path, "rb") as f:
                if f.read() == data:
                    return StoredArtifact(
                        key=key, uri=f"file://{path}",
                        size_bytes=len(data), content_type=content_type,
                    )
        with open(path, "wb") as f:
            f.write(data)
        return StoredArtifact(
            key=key, uri=f"file://{path}",
            size_bytes=len(data), content_type=content_type,
        )

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))

    def get_local_path(self, key: str) -> str:
        path = self._path(key)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        return path

    def presigned_get_url(self, key: str, *, ttl_seconds: int = 300) -> str:
        # No real presign for local-disk; the FastAPI download endpoint is
        # the equivalent. Returning the route the customer should fetch
        # through, not a direct file:// URL.
        return f"/launchpad/coldcase/api/artifacts/{key}"


class AzureBlobArtifactStore:
    """Phase-B stub. Real implementation uses azure-storage-blob with the
    customer's tenant + container. Cold Case writes the artifact, the bytes
    live in the customer's Azure storage (not ours), and downstream readers
    fetch via signed URL — consistent with rule #17 data residency."""

    name = "azure_blob"

    def put(self, key: str, data: bytes, *, content_type: str) -> StoredArtifact:
        raise NotImplementedError(
            "AzureBlobArtifactStore is not yet wired. "
            "Set COLDCASE_ARTIFACT_STORE=local for development."
        )

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def get_local_path(self, key: str) -> str:
        raise NotImplementedError(
            "Azure blob requires temp-file materialization; not yet implemented."
        )

    def presigned_get_url(self, key: str, *, ttl_seconds: int = 300) -> str:
        raise NotImplementedError


def get_artifact_store() -> ArtifactStore:
    choice = os.environ.get("COLDCASE_ARTIFACT_STORE", "local").lower()
    if choice == "local":
        return LocalArtifactStore()
    if choice in ("azure", "azure_blob"):
        return AzureBlobArtifactStore()
    raise ValueError(f"Unknown COLDCASE_ARTIFACT_STORE={choice!r}")
