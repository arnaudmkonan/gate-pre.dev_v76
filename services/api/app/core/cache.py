"""
GATE Platform — Redis Caching Layer.

Provides a decorator-based caching system for expensive lookups.
Falls back gracefully when Redis is unavailable.
"""
import json
import hashlib
import logging
import functools
from datetime import timedelta
from typing import Optional, Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

# Singleton Redis connection (lazy init)
_redis_client = None


def _get_redis():
    """Get or create Redis client (lazy singleton)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=3,  # Separate DB from Celery (0), results (2)
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()
        logger.info("Cache: Redis connected (db=3)")
        return _redis_client
    except Exception as e:
        logger.warning(f"Cache: Redis unavailable, caching disabled ({e})")
        _redis_client = None
        return None


def cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Build a deterministic cache key.

    Example: cache_key("hts", "8471.30") -> "gate:hts:8471.30"
    """
    parts = [str(a) for a in args]
    if kwargs:
        sorted_kw = sorted(kwargs.items())
        parts.extend(f"{k}={v}" for k, v in sorted_kw)
    raw = ":".join(parts)
    return f"gate:{prefix}:{raw}"


def get_cached(key: str) -> Optional[Any]:
    """Get value from cache. Returns None on miss or error."""
    r = _get_redis()
    if r is None:
        return None
    try:
        value = r.get(key)
        if value is not None:
            return json.loads(value)
    except Exception as e:
        logger.debug(f"Cache get error: {e}")
    return None


def set_cached(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Set value in cache with TTL. Returns False on error."""
    r = _get_redis()
    if r is None:
        return False
    try:
        serialized = json.dumps(value, default=str)
        r.setex(key, ttl_seconds, serialized)
        return True
    except Exception as e:
        logger.debug(f"Cache set error: {e}")
        return False


def invalidate(key: str) -> bool:
    """Delete a cache key."""
    r = _get_redis()
    if r is None:
        return False
    try:
        r.delete(key)
        return True
    except Exception:
        return False


def invalidate_pattern(pattern: str) -> int:
    """Delete all cache keys matching a pattern. Returns count deleted."""
    r = _get_redis()
    if r is None:
        return 0
    try:
        keys = r.keys(f"gate:{pattern}")
        if keys:
            return r.delete(*keys)
        return 0
    except Exception:
        return 0


def cached(prefix: str, ttl: int = 300):
    """
    Decorator for caching function results.

    Usage:
        @cached("hts", ttl=86400)
        async def lookup_hts_code(code: str) -> dict:
            ...

    Works with both sync and async functions.
    Cache key is built from function args.
    """
    def decorator(func: Callable):
        if _is_async(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = cache_key(prefix, *args, **kwargs)
                result = get_cached(key)
                if result is not None:
                    return result
                result = await func(*args, **kwargs)
                if result is not None:
                    set_cached(key, result, ttl)
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                key = cache_key(prefix, *args, **kwargs)
                result = get_cached(key)
                if result is not None:
                    return result
                result = func(*args, **kwargs)
                if result is not None:
                    set_cached(key, result, ttl)
                return result
            return sync_wrapper
    return decorator


def _is_async(func):
    """Check if a function is async."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


def get_cache_stats() -> dict:
    """Get cache statistics for health endpoint."""
    r = _get_redis()
    if r is None:
        return {"status": "unavailable", "reason": "Redis not connected"}

    try:
        info = r.info("memory")
        keys = r.dbsize()
        return {
            "status": "ok",
            "keys": keys,
            "used_memory": info.get("used_memory_human", "unknown"),
            "max_memory": info.get("maxmemory_human", "unknown"),
            "hit_rate": "n/a",  # Would need keyspace_hits/misses
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
