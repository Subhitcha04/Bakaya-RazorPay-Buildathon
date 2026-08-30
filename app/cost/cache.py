"""
Diagnosis cache key (decline reasons repeat heavily across customers,
so caching on the normalized signature eliminates a large share of
Tier-2 calls before they happen), backed by a small dependency-free
TTL cache.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


def normalize_description(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.lower().split())


def diagnosis_cache_key(
    error_code: str | None, error_source: str | None,
    error_step: str | None, error_description: str | None,
) -> str:
    normalized = normalize_description(error_description)
    material = f"{error_code}|{error_source}|{error_step}|{normalized}"
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass
class CacheEntry:
    value: object
    stored_at: float


class TTLCache:
    def __init__(self, ttl_seconds: float = 3600):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str, now: float | None = None):
        now = now if now is not None else time.time()
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        if now - entry.stored_at > self.ttl_seconds:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry.value

    def set(self, key: str, value, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        self._store[key] = CacheEntry(value=value, stored_at=now)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def size(self) -> int:
        return len(self._store)
