"""Small TTL cache utilities used by the customer service agent.

The cache is intentionally dependency-free and process-local.  It is suitable for
reducing repeated reads during demos, tests, and single-process deployments.  In
a horizontally scaled production deployment, replace this module with Redis or
another shared cache while keeping the same high-level get/set/invalidate calls.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")
_MISSING = object()


@dataclass(frozen=True)
class CacheStats:
    """Runtime counters that make cache behavior observable in tests/logging."""

    hits: int
    misses: int
    size: int


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Thread-safe in-memory cache with per-entry time-to-live expiration."""

    def __init__(self, ttl_seconds: float = 300, max_size: int = 512, clock: Callable[[], float] | None = None):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_size <= 0:
            raise ValueError("max_size must be greater than zero")
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._clock = clock or time.monotonic
        self._entries: dict[Hashable, _CacheEntry[T]] = {}
        self._lock = RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: Hashable, default: T | object = _MISSING) -> T | object:
        with self._lock:
            entry = self._entries.get(key)
            now = self._clock()
            if entry is None:
                self._misses += 1
                return default
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                self._misses += 1
                return default
            self._hits += 1
            return entry.value

    def set(self, key: Hashable, value: T) -> None:
        with self._lock:
            self._purge_expired_locked()
            if len(self._entries) >= self.max_size and key not in self._entries:
                oldest_key = min(self._entries, key=lambda existing_key: self._entries[existing_key].expires_at)
                self._entries.pop(oldest_key, None)
            self._entries[key] = _CacheEntry(value=value, expires_at=self._clock() + self.ttl_seconds)

    def get_or_set(self, key: Hashable, factory: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not _MISSING:
            return cached  # type: ignore[return-value]
        value = factory()
        self.set(key, value)
        return value

    def invalidate(self, key: Hashable) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> CacheStats:
        with self._lock:
            self._purge_expired_locked()
            return CacheStats(hits=self._hits, misses=self._misses, size=len(self._entries))

    def _purge_expired_locked(self) -> None:
        now = self._clock()
        expired_keys = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired_keys:
            self._entries.pop(key, None)


def cache_enabled() -> bool:
    return os.getenv("CUSTOMER_SERVICE_CACHE_ENABLED", "1") != "0"


def cache_ttl_seconds() -> float:
    return float(os.getenv("CUSTOMER_SERVICE_CACHE_TTL_SECONDS", "300"))


def cache_max_size() -> int:
    return int(os.getenv("CUSTOMER_SERVICE_CACHE_MAX_SIZE", "512"))
