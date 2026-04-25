import redis
import json
import hashlib
from typing import Optional
from app.core.config import settings

# ── Redis client ──────────────────────────────────────────
_redis_client = None


def get_redis() -> Optional[redis.Redis]:
    """
    Get Redis client. Returns None if Redis is unavailable.
    This allows the app to work without Redis (graceful degradation).
    """
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
            print("✅ Redis connected")
        except Exception as e:
            print(f"⚠️  Redis unavailable ({e}) — caching disabled")
            _redis_client = None

    return _redis_client


def make_cache_key(prefix: str, **kwargs) -> str:
    """
    Generate a consistent cache key from a prefix and parameters.

    Example:
        make_cache_key("search", query="machine learning", limit=5)
        → "search:a3f2b1c4..."
    """
    payload = json.dumps(kwargs, sort_keys=True)
    hash_val = hashlib.md5(payload.encode()).hexdigest()[:12]
    return f"projectlens:{prefix}:{hash_val}"


def cache_get(key: str) -> Optional[dict]:
    """Get a cached value. Returns None if not found or Redis unavailable."""
    client = get_redis()
    if not client:
        return None

    try:
        value = client.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        print(f"⚠️  Cache get failed: {e}")

    return None


def cache_set(key: str, value: dict, ttl: int = 3600) -> bool:
    """
    Store a value in cache with TTL in seconds.

    TTL guidelines for Project Lens:
    - Search results:     1 hour  (3600s)  — papers don't change often
    - Dataset results:    2 hours (7200s)  — Kaggle data is stable
    - GitHub repos:       30 min  (1800s)  — repos update more often
    - Trending papers:    6 hours (21600s) — trends are slow moving
    - Novelty checks:     1 hour  (3600s)  — same idea = same score
    """
    client = get_redis()
    if not client:
        return False

    try:
        client.setex(key, ttl, json.dumps(value))
        return True
    except Exception as e:
        print(f"⚠️  Cache set failed: {e}")
        return False


def cache_delete(key: str) -> bool:
    """Delete a cached value."""
    client = get_redis()
    if not client:
        return False

    try:
        client.delete(key)
        return True
    except Exception as e:
        print(f"⚠️  Cache delete failed: {e}")
        return False


def cache_stats() -> dict:
    """Get cache statistics for the health endpoint."""
    client = get_redis()
    if not client:
        return {"status": "unavailable", "keys": 0}

    try:
        info = client.info()
        keys = client.dbsize()
        return {
            "status": "connected",
            "keys": keys,
            "memory_used": info.get("used_memory_human", "unknown"),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": _calculate_hit_rate(
                info.get("keyspace_hits", 0),
                info.get("keyspace_misses", 0)
            ),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _calculate_hit_rate(hits: int, misses: int) -> str:
    total = hits + misses
    if total == 0:
        return "0%"
    return f"{round((hits / total) * 100, 1)}%"