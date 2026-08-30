"""
Declarative base + shared mixins.

Portability note: primary keys are String(36) UUIDs rather than native
Postgres UUID or BIGSERIAL, specifically so this schema can be smoke-tested
against SQLite in dev/CI without a running Postgres instance. Production
deploys on Postgres/Neon; swap to postgresql.UUID(as_uuid=True) for native
storage if you want it -- application-level behaviour is identical either way.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
