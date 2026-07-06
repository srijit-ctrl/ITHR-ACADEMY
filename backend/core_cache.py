"""Simple in-memory TTL cache with an async decorator.

Purpose: hot dashboards (platform analytics, admin orgs list, courses catalog)
were being served from raw MongoDB queries on every request. On a busy pod
this multiplies cursor round-trips 100x — the same "who signed up in the
last 30 days?" aggregation would run for every reload of /admin.

This module gives each pod its own thread-safe TTL cache. It is deliberately
NOT distributed (no Redis) because:

1. Emergent-managed pods run 1–2 replicas — the per-pod duplication is
   negligible compared to the compute saved.
2. Adding Redis would introduce another infra dependency + failure mode.
3. TTLs are short (60–180s) so eventual consistency is fine for dashboards.

For hard invalidation on a write (e.g. a super-admin bumps a course version),
call `bust(prefix=…)` from the mutating endpoint. There is also a
`POST /api/admin/cache/purge` super-admin endpoint (see admin_router) for
operational emergencies.

Usage:

    from core_cache import cached

    @cached(ttl_seconds=120, key_prefix="platform_analytics")
    async def platform_analytics(days: int = 30) -> dict:
        ...

The decorator hashes positional + keyword args into the cache key so the
same function called with different args caches independently.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from functools import wraps
from threading import RLock
from typing import Any, Callable

_lock = RLock()
_store: dict[str, tuple[float, Any]] = {}  # key -> (expires_at_epoch, value)


def _now() -> float:
    return time.monotonic()


def _make_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Deterministic cache key from prefix + args + kwargs."""
    try:
        payload = json.dumps({"a": list(args), "k": kwargs}, sort_keys=True, default=str)
    except Exception:
        payload = repr((args, kwargs))
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


def get(key: str) -> Any | None:
    """Return cached value if present + fresh, else None. Silently evicts expired entries."""
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if _now() >= expires_at:
            _store.pop(key, None)
            return None
        return value


def set_(key: str, value: Any, ttl_seconds: float) -> None:
    with _lock:
        _store[key] = (_now() + ttl_seconds, value)


def bust(prefix: str | None = None) -> int:
    """Drop cache entries. Returns count of entries removed.

    - `bust()` clears the entire cache (nuclear).
    - `bust(prefix="courses")` drops only entries whose key starts with `courses:`.
    """
    with _lock:
        if prefix is None:
            n = len(_store)
            _store.clear()
            return n
        to_drop = [k for k in _store if k.startswith(f"{prefix}:")]
        for k in to_drop:
            _store.pop(k, None)
        return len(to_drop)


def stats() -> dict:
    """Return light diagnostic info (for /api/admin/cache/purge to show what was cleared)."""
    with _lock:
        now = _now()
        fresh = sum(1 for exp, _ in _store.values() if exp > now)
        stale = len(_store) - fresh
        return {"entries_total": len(_store), "entries_fresh": fresh, "entries_stale": stale}


def cached(ttl_seconds: float, key_prefix: str):
    """Async function decorator applying process-local TTL caching.

    Only supports coroutine functions — we intentionally do not want to
    silently mis-use this on sync helpers.
    """
    def decorator(fn: Callable):
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError(f"@cached only supports async functions; {fn.__name__} is sync")

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            key = _make_key(key_prefix, args, kwargs)
            hit = get(key)
            if hit is not None:
                return hit
            value = await fn(*args, **kwargs)
            set_(key, value, ttl_seconds)
            return value

        # Expose bust() for the specific prefix so callers can do
        #   platform_analytics.bust()
        wrapper.bust = lambda: bust(prefix=key_prefix)  # type: ignore[attr-defined]
        return wrapper

    return decorator
