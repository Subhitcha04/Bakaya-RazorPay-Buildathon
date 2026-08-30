from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/bakaya")

# check_same_thread=False is required for ANY SQLite-backed FastAPI
# deployment, not just this one -- FastAPI runs sync dependencies (like
# get_db below) in a worker threadpool, and a bare sqlite3 connection
# object refuses cross-thread use by default, which would surface as
# an intermittent "SQLite objects created in a thread can only be used
# in that same thread" error under real request concurrency. Irrelevant
# for Postgres, so gated on the URL prefix rather than applied
# unconditionally. This was a genuine latent bug -- found while wiring
# up app/api/server.py, which is the first place in this repo that
# actually serves a SQLite-backed engine through FastAPI's dependency
# system rather than a test's manually-constructed session.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
