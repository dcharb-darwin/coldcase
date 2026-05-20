"""Hash-chained audit log integrity helpers.

Each tenant's `AuditEvent` collection is treated as an append-only chain.
Every event carries:

  - `sequence`        — monotonic per tenant
  - `prev_event_hash` — sha256 of the previous event's `event_hash`
  - `event_hash`      — sha256 of `prev_event_hash || canonical(this)`

A break anywhere in the chain (deleted row, mutated field, reordered
timestamp) shows up as a hash mismatch under `verify_chain`. Whether a
tenant cares to ship the chain off-box for stronger anchoring is a future
exercise — what's here is the local courtroom-grade tamper-evidence the
compliance status doc claimed existed.

Concurrency model: two simultaneous insert callers will collide on the
same `(tenant_id, sequence)` unique index. The loser re-reads the latest
event and retries, so the chain stays linear.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from models.audit_event import AuditEvent, GENESIS_PREV_HASH

logger = logging.getLogger(__name__)

MAX_INSERT_RETRIES = 5

# Fields that participate in the canonical content hash. Order matters
# only inside this list (the JSON dump uses `sort_keys=True`); add new
# fields at the bottom so existing hashes are stable when the schema grows.
_CANONICAL_FIELDS = (
    "tenant_id",
    "timestamp",
    "event_type",
    "user_id",
    "user_display",
    "ip_address",
    "case_id",
    "conversation_id",
    "message_id",
    "report_id",
    "document_id",
    "media_id",
    "summary",
    "detail",
    "sequence",
    "prev_event_hash",
)


def _canonical_payload(event: AuditEvent) -> str:
    """Stable JSON representation of the event's content. Sorted keys,
    no whitespace, ISO-format timestamps. Same string here at write-time
    and at verify-time.

    BSON only stores datetime at millisecond precision, so we truncate
    the microsecond component before serialising — otherwise the write-time
    hash uses a fractional microsecond that the read-back value has lost.
    """
    payload: dict[str, Any] = {}
    for f in _CANONICAL_FIELDS:
        v = getattr(event, f, None)
        if hasattr(v, "isoformat"):  # datetime
            try:
                # Drop sub-millisecond precision to match BSON round-trip.
                v = v.replace(microsecond=(v.microsecond // 1000) * 1000)
            except Exception:  # noqa: BLE001 — `date` has no microsecond
                pass
            v = v.isoformat()
        if isinstance(v, dict):
            v = dict(v)  # MongoEngine DictField — coerce to plain dict
        payload[f] = v if v is not None else ""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(event: AuditEvent) -> str:
    """sha256 of `prev_event_hash || canonical(event)` as hex."""
    return hashlib.sha256(_canonical_payload(event).encode("utf-8")).hexdigest()


def latest_event(tenant_id: str) -> AuditEvent | None:
    """The newest sequenced event for the tenant, or None on a cold start."""
    return (
        AuditEvent
        .objects(tenant_id=tenant_id, sequence__exists=True)
        .order_by("-sequence")
        .first()
    )


def insert_chained(event: AuditEvent) -> AuditEvent:
    """Insert with sequence + chain hashes. Caller passes an unsaved
    `AuditEvent`; this function fills in `sequence`, `prev_event_hash`,
    `event_hash`, and saves. Retries on unique-index collisions when two
    writers race for the same sequence number.

    Raises after MAX_INSERT_RETRIES — the caller treats that as the audit
    write failing (which the cold-case `case_audit.log` already swallows
    rather than aborting the user's action)."""
    from mongoengine.errors import NotUniqueError  # local import — heavy

    for attempt in range(MAX_INSERT_RETRIES):
        prior = latest_event(event.tenant_id)
        event.sequence = (prior.sequence + 1) if prior else 0
        event.prev_event_hash = prior.event_hash if prior else GENESIS_PREV_HASH
        event.event_hash = compute_event_hash(event)
        try:
            event.save(force_insert=True)
            return event
        except NotUniqueError:
            # Another writer grabbed our sequence; recompute against the new latest.
            logger.info(
                "Audit chain insert collision at sequence=%s, retrying (attempt %d)",
                event.sequence, attempt + 1,
            )
            event.id = None  # force a new ObjectId on retry
            continue
    raise RuntimeError(
        f"Audit chain insert failed after {MAX_INSERT_RETRIES} retries for tenant "
        f"{event.tenant_id!r}"
    )


# ── Verification ───────────────────────────────────────────────────────────


def verify_chain(tenant_id: str) -> dict:
    """Walk the tenant's audit chain in sequence order. Recompute every
    event's hash from its stored canonical payload and verify it matches
    `event_hash` AND that `prev_event_hash` matches the actual previous
    event's `event_hash`. Returns a structured report.

    Caller (admin endpoint, chain PDF rendering, compliance preflight)
    decides what to do with breaks — usually surface them in the UI and
    flag the city attorney."""
    events = list(
        AuditEvent
        .objects(tenant_id=tenant_id, sequence__exists=True)
        .order_by("sequence")
    )
    breaks: list[dict] = []
    expected_prev = GENESIS_PREV_HASH
    for i, e in enumerate(events):
        if e.sequence != i:
            breaks.append({
                "sequence": e.sequence,
                "index": i,
                "kind": "sequence_gap",
                "detail": f"Expected sequence {i}, found {e.sequence}",
                "event_id": str(e.id),
            })
        if e.prev_event_hash != expected_prev:
            breaks.append({
                "sequence": e.sequence,
                "index": i,
                "kind": "prev_hash_mismatch",
                "detail": f"prev_event_hash {e.prev_event_hash[:12]}… "
                          f"did not match previous event's hash {expected_prev[:12]}…",
                "event_id": str(e.id),
            })
        recomputed = compute_event_hash(e)
        if e.event_hash != recomputed:
            breaks.append({
                "sequence": e.sequence,
                "index": i,
                "kind": "event_hash_mismatch",
                "detail": f"Stored hash {e.event_hash[:12]}… "
                          f"did not match recomputed {recomputed[:12]}…",
                "event_id": str(e.id),
            })
        expected_prev = e.event_hash

    pre_chain = AuditEvent.objects(
        tenant_id=tenant_id, sequence__exists=False,
    ).count()

    return {
        "tenant_id": tenant_id,
        "ok": len(breaks) == 0,
        "event_count": len(events),
        "pre_chain_event_count": pre_chain,
        "tip_hash": events[-1].event_hash if events else GENESIS_PREV_HASH,
        "breaks": breaks,
    }


# ── Backfill (one-shot at startup) ─────────────────────────────────────────


def rechain_all(tenant_id: str) -> dict:
    """Wipe `sequence` / `prev_event_hash` / `event_hash` on every event in
    the tenant, then re-stamp from scratch. Use sparingly — intended for
    one-shot repair when the hash canonical changes (or a bug like the
    initial microsecond-vs-millisecond mismatch is fixed).

    Insertion order matches the original event ordering by (timestamp, _id)."""
    cleared = AuditEvent.objects(tenant_id=tenant_id).update(
        unset__sequence=True,
        unset__prev_event_hash=True,
        unset__event_hash=True,
    )
    logger.info("Audit chain reset: cleared %d events for tenant %s", cleared, tenant_id)
    return {"cleared": cleared, **backfill_chain(tenant_id)}


def backfill_chain(tenant_id: str) -> dict:
    """Stamp `sequence`, `prev_event_hash`, and `event_hash` onto any
    pre-chain rows. Idempotent: rows that already have a sequence are
    skipped. Insertion order is `(timestamp, _id)` so the chain matches
    the order events were actually written.

    Runs at app startup so a tenant that upgraded through the schema
    addition doesn't need a manual migration step."""
    pre = AuditEvent.objects(tenant_id=tenant_id, sequence__exists=False).order_by("timestamp", "id")
    count_pre = pre.count()
    if count_pre == 0:
        return {"stamped": 0, "already_chained": AuditEvent.objects(
            tenant_id=tenant_id, sequence__exists=True,
        ).count()}

    prior = latest_event(tenant_id)
    expected_prev = prior.event_hash if prior else GENESIS_PREV_HASH
    next_seq = (prior.sequence + 1) if prior else 0

    stamped = 0
    for e in pre:
        e.sequence = next_seq
        e.prev_event_hash = expected_prev
        e.event_hash = compute_event_hash(e)
        e.save()
        expected_prev = e.event_hash
        next_seq += 1
        stamped += 1
    logger.info("Audit chain backfill: stamped %d events for tenant %s", stamped, tenant_id)
    return {
        "stamped": stamped,
        "already_chained": AuditEvent.objects(
            tenant_id=tenant_id, sequence__exists=True,
        ).count() - stamped,
    }
