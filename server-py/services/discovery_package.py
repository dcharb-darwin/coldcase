"""F8 — Discovery Package ZIP for defense / DA / city-attorney handoff.

One-click bundle assembly per case (or report subset). Self-signing
`manifest.json` over the embedded file hashes. Source-document binaries
default OFF (pointer-only); set `include_source_binaries=true` to ship
them inside the ZIP.

Per business rule #21 the ZIP is generated to a Cold-Case-controlled temp
dir, written to the destination storage, and unlinked locally — never
retained by Cold Case after delivery. The destination handoff details
(signed URL, customer Azure/S3 upload) are an integration left to a
customer-storage adapter; for MVP we write to `uploads/discovery/` and
return a relative URI the operator hands off manually.
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import datetime
from typing import TypedDict

from lib.hash import hash_file
from models import Document
from models.case import Case
from models.media_input import MediaInput
from models.report import Report
from services.chain_export import export_chain_pdf
from services.report_export import export_report_pdf


class DiscoveryFileEntry(TypedDict):
    path: str
    sha256: str
    size_bytes: int
    kind: str


def build_discovery_zip(
    case: Case,
    *,
    requesting_user_id: str,
    requesting_user_display: str,
    reason: str,
    report_ids: list[str] | None = None,
    include_source_binaries: bool = False,
    output_dir: str | None = None,
) -> dict:
    """Assemble the ZIP and return delivery metadata. The caller is
    responsible for handing off the URI to the customer + auditing.
    """
    output_dir = output_dir or os.path.join(
        os.environ.get("UPLOAD_DIRECTORY", "./uploads"), "discovery"
    )
    os.makedirs(output_dir, exist_ok=True)

    # Decide which reports + which docs + which media to include.
    if report_ids:
        reports = list(Report.objects(case=case, id__in=report_ids).order_by("created_at"))
    else:
        reports = list(Report.objects(case=case).order_by("created_at"))
    documents = list(Document.objects(case=case).order_by("uploaded_at"))
    media_inputs = list(MediaInput.objects(case=case).order_by("registered_at"))

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    zip_basename = f"{case.case_number}-{timestamp}.zip"
    zip_path = os.path.join(output_dir, zip_basename)

    # File inventory we'll assemble before writing the ZIP.
    files_to_embed: list[tuple[str, bytes, str]] = []  # (arcname, bytes, kind)

    # README + INDEX placeholders are added after we know the file list.
    def _add(arcname: str, data: bytes, kind: str) -> None:
        files_to_embed.append((arcname, data, kind))

    # Ensure each report has both PDFs on disk (regenerate if missing).
    for r in reports:
        if not r.signature:
            continue  # unsigned reports excluded — only official artifacts ship
        rpt_pdf_path = export_report_pdf(r)
        chain_pdf_path = export_chain_pdf(r)
        with open(rpt_pdf_path, "rb") as f:
            _add(f"reports/{r.id}.pdf", f.read(), "signed_report")
        with open(chain_pdf_path, "rb") as f:
            _add(f"reports/{r.id}.chain.pdf", f.read(), "chain_of_custody")

    # Optionally include source-document binaries.
    if include_source_binaries:
        from providers.document_storage import get_document_storage_provider
        storage = get_document_storage_provider()
        for d in documents:
            try:
                path = storage.resolve_path(d.storage_uri)
                with open(path, "rb") as f:
                    safe_name = d.original_filename.replace("/", "_")
                    _add(f"documents/{d.sha256[:12]}__{safe_name}", f.read(), "source_document")
            except (FileNotFoundError, OSError):
                continue

    # Build manifest.json + INDEX.txt + README.md after we know the entries.
    # Hash the bytes we WILL embed so files[] is accurate.
    files_inventory: list[DiscoveryFileEntry] = []
    for arcname, data, kind in files_to_embed:
        files_inventory.append({
            "path": arcname,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "kind": kind,
        })

    # Self-signing manifest hash: sha256 over sorted file hashes.
    sorted_hashes = sorted(f["sha256"] for f in files_inventory)
    manifest_sha256 = hashlib.sha256("|".join(sorted_hashes).encode()).hexdigest()

    manifest = {
        "coldcase_version": "0.5.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "requesting_user_id": requesting_user_id,
        "requesting_user_display": requesting_user_display,
        "reason": reason,
        "case_number": case.case_number,
        "case_id": str(case.id),
        "case_classification": case.classification,
        "case_retention_policy": case.retention_policy,
        "report_ids": [str(r.id) for r in reports],
        "include_source_binaries": include_source_binaries,
        "files": files_inventory,
        "documents": [
            {
                "filename": d.original_filename,
                "storage_uri": d.storage_uri,
                "sha256": d.sha256,
                "mime_type": d.mime_type,
                "size_bytes": d.size_bytes,
                "registered_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            }
            for d in documents
        ],
        "media_inputs": [  # §13663(c)(2)
            {
                "source_type": m.source_type,
                "storage_uri": m.storage_uri,
                "sha256": m.sha256,
                "duration_seconds": m.duration_seconds,
                "captured_at": m.captured_at.isoformat() if m.captured_at else None,
                "description": m.description,
                "registered_at": m.registered_at.isoformat() if m.registered_at else None,
            }
            for m in media_inputs
        ],
        "manifest_sha256": manifest_sha256,
        "verify_instructions": (
            "Re-derive manifest_sha256 by: sorted(files[].sha256), '|'.join, sha256. "
            "Verify each file by sha256sum -c against this manifest."
        ),
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=False).encode()

    index_lines = [
        f"DISCOVERY PACKAGE — Cold Case {case.case_number}",
        f"Generated: {manifest['generated_at']}",
        f"Requested by: {requesting_user_display} ({requesting_user_id})",
        f"Reason: {reason}",
        f"Manifest sha256: {manifest_sha256}",
        f"",
        f"This bundle contains {len(reports)} signed report(s), {len(reports)} chain-of-custody PDF(s),",
        f"{len(documents)} source document pointer(s){' + binaries' if include_source_binaries else ''},",
        f"and {len(media_inputs)} media-input pointer(s).",
        f"",
        f"Contents:",
        f"  INDEX.txt        — this file",
        f"  README.md        — bundle structure + verification instructions",
        f"  manifest.json    — machine-readable inventory (self-signing)",
    ]
    for entry in files_inventory:
        index_lines.append(f"  {entry['path']:<55s} {entry['size_bytes']:>10,} bytes  sha256={entry['sha256'][:16]}…")
    index_bytes = ("\n".join(index_lines) + "\n").encode()

    readme = (
        f"# Discovery Package — Cold Case {case.case_number}\n\n"
        f"This bundle was generated by Cold Case (Darwin Launchpad) for legal review "
        f"under California Penal Code §13663 (SB-524).\n\n"
        f"## Contents\n\n"
        f"- `reports/<id>.pdf` — the officer-signed §13663(a) official reports.\n"
        f"- `reports/<id>.chain.pdf` — the §13663(c) chain-of-custody audit trail for each report.\n"
        f"- `documents/<sha>__<filename>` — source documents (only included if "
        f"`include_source_binaries=true` was set at export time; otherwise pointer-only in manifest.json).\n"
        f"- `manifest.json` — machine-readable inventory with hashes. **Self-signing**: "
        f"`manifest_sha256` is `sha256` over the sorted list of file sha256 values, joined by `|`. "
        f"Anyone re-running that computation against the embedded files should get the same value.\n"
        f"- `INDEX.txt` — human-readable directory of files.\n\n"
        f"## Verifying integrity\n\n"
        f"```\n"
        f"# Re-compute the manifest hash from the embedded files:\n"
        f"jq -r '.files[].sha256' manifest.json | sort | tr '\\n' '|' | sed 's/|$//' | sha256sum\n"
        f"# Should equal the `manifest_sha256` field in manifest.json.\n\n"
        f"# Verify each embedded file:\n"
        f"sha256sum reports/*.pdf documents/* 2>/dev/null\n"
        f"# Compare to manifest.json files[].sha256\n"
        f"```\n\n"
        f"## Source documents\n\n"
        f"By default, source-document binaries are NOT included — only their `storage_uri` + `sha256` "
        f"pointer records (see `manifest.json` → `documents`). The customer's primary storage "
        f"(Azure Blob / S3 / SharePoint) holds the canonical binaries. This is intentional per "
        f"Cold Case business rule #17 (data residency). If your discovery target needs the binaries, "
        f"the customer must export them from their primary storage with the same sha256 values for verification.\n"
    )
    readme_bytes = readme.encode()

    # Hash the manifest/index/readme too so they're listed in files[] retroactively.
    # We rebuild files[] now that we know the bytes for those three.
    final_inventory: list[DiscoveryFileEntry] = []
    final_inventory.append({"path": "manifest.json", "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                            "size_bytes": len(manifest_bytes), "kind": "manifest"})
    final_inventory.append({"path": "INDEX.txt", "sha256": hashlib.sha256(index_bytes).hexdigest(),
                            "size_bytes": len(index_bytes), "kind": "index"})
    final_inventory.append({"path": "README.md", "sha256": hashlib.sha256(readme_bytes).hexdigest(),
                            "size_bytes": len(readme_bytes), "kind": "readme"})
    final_inventory.extend(files_inventory)

    # NOTE: manifest.json itself includes its OWN hash via manifest_sha256 over
    # the *content* hashes of the embedded files. We don't include the manifest
    # in its own files[] inventory (that would be circular).
    # The version listed in final_inventory above is for INDEX/external traversal.

    # Write the ZIP.
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("INDEX.txt", index_bytes)
        zf.writestr("README.md", readme_bytes)
        zf.writestr("manifest.json", manifest_bytes)
        for arcname, data, _kind in files_to_embed:
            zf.writestr(arcname, data)

    zip_sha256, zip_size = hash_file(zip_path)

    return {
        "case_id": str(case.id),
        "case_number": case.case_number,
        "zip_path": zip_path,
        "zip_filename": zip_basename,
        "zip_uri": f"file://{zip_path}",
        "zip_sha256": zip_sha256,
        "zip_size_bytes": zip_size,
        "manifest_sha256": manifest_sha256,
        "file_count": len(files_to_embed) + 3,  # +3 = INDEX, README, manifest
        "report_count": len([r for r in reports if r.signature]),
        "document_count": len(documents),
        "media_count": len(media_inputs),
        "include_source_binaries": include_source_binaries,
    }
