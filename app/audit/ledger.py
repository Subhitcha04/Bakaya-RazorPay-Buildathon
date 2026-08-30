"""
Append-only, hash-chained audit ledger. Every consequential action --
grants, blocks, escalations, executions, refusals -- gets exactly one
entry, always through append() below. Blocks are audited with the same
rigour as sends; that's the whole point of the design.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEntry

GENESIS_HASH = "0" * 64


def _canonical(payload: dict) -> str:
    # sort_keys -> deterministic serialization, so the hash is reproducible
    # regardless of dict insertion order.
    return json.dumps(payload, sort_keys=True, default=str)


def _compute_hash(seq: int, prev_hash: str, payload: dict) -> str:
    material = f"{seq}|{prev_hash}|{_canonical(payload)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _last_entry(db: Session) -> AuditEntry | None:
    stmt = select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1)
    return db.execute(stmt).scalars().first()


def append(db: Session, event_type: str, payload: dict) -> AuditEntry:
    """
    The ONLY way an audit_entry row should ever be created. Never build
    one by hand elsewhere in the codebase -- chain integrity depends on
    every entry going through this single function so seq/prev_hash stay
    consistent under concurrent writers.
    """
    last = _last_entry(db)
    seq = (last.seq + 1) if last else 0
    prev_hash = last.hash if last else GENESIS_HASH

    entry_hash = _compute_hash(seq, prev_hash, payload)
    entry = AuditEntry(
        seq=seq,
        event_type=event_type,
        case_id=payload.get("case_id"),   # auto-populated for indexed lookup -- see AuditEntry's docstring
        prev_hash=prev_hash,
        payload_json=payload,
        hash=entry_hash,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def verify_chain(db: Session) -> tuple[bool, int | None]:
    """
    Walks the whole chain from genesis. Returns (True, None) if intact,
    or (False, seq) pointing at the first broken link. This is what
    `make verify-audit` calls -- see audit/cli.py.
    """
    stmt = select(AuditEntry).order_by(AuditEntry.seq.asc())
    entries = db.execute(stmt).scalars().all()

    expected_prev = GENESIS_HASH
    for entry in entries:
        if entry.prev_hash != expected_prev:
            return False, entry.seq
        recomputed = _compute_hash(entry.seq, entry.prev_hash, entry.payload_json)
        if recomputed != entry.hash:
            return False, entry.seq
        expected_prev = entry.hash
    return True, None

