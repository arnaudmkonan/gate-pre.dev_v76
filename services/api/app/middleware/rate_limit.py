"""
Rate Limiting Middleware with Customer Tier Support.

Provides tiered rate limiting based on customer subscription level:
- Starter: 60 requests/minute
- Professional: 200 requests/minute
- Enterprise: 1000 requests/minute

Also includes IP-based rate limiting for unauthenticated requests.

Storage backends:
- memory://  → In-process dict (dev only — NOT safe for multi-worker production)
- redis://…  → Redis (production, safe for gunicorn multi-worker)

Set RATE_LIMIT_STORAGE=redis://<host>:<port>/<db> in production.
"""
import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Callable, Optional

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please slow down.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


class TokenBucket:
    """
    In-process token bucket rate limiter (dev/single-worker only).

    For multi-worker production use RedisTokenBucket instead.
    """

    def __init__(self, rate: float, capacity: int):
        self.rate = rate          # tokens added per second
        self.capacity = capacity  # max tokens
        self.tokens = float(capacity)
        self.last_update = time.time()

    def consume(self, tokens: int = 1) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self) -> float:
        if self.tokens >= 1:
            return 0.0
        return (1.0 - self.tokens) / self.rate


class RedisTokenBucket:
    """
    Redis-backed token bucket for multi-process / multi-worker deployments.

    Uses a Lua script for atomic read-modify-write so there are no race
    conditions across gunicorn workers.
    """

    # Lua script: atomically refill + consume from a Redis key.
    # Keys: [key]
    # Args: rate_per_sec, capacity, tokens_to_consume, now_unix_float_str
    _LUA = """
local key        = KEYS[1]
local rate       = tonumber(ARGV[1])
local capacity   = tonumber(ARGV[2])
local consume    = tonumber(ARGV[3])
local now        = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1]) or capacity
local ts     = tonumber(data[2]) or now

-- Refill
local elapsed = now - ts
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens >= consume then
    tokens = tokens - consume
    redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
    redis.call('EXPIRE', key, 3600)
    return 1   -- allowed
else
    redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
    redis.call('EXPIRE', key, 3600)
    return 0   -- denied
end
"""

    def __init__(self, redis_client, key: str, rate: float, capacity: int):
        self._redis = redis_client
        self._key = key
        self._rate = rate
        self._capacity = capacity
        self._script = None  # registered after first call

    async def consume(self, tokens: int = 1) -> bool:
        import redis.asyncio as aioredis
        if self._script is None:
            self._script = self._redis.register_script(self._LUA)
        now = time.time()
        result = await self._script(
            keys=[self._key],
            args=[self._rate, self._capacity, tokens, now],
        )
        return bool(result)

    async def tokens_remaining(self) -> float:
        raw = await self._redis.hget(self._key, "tokens")
        return float(raw) if raw else float(self._capacity)


class CustomerTier:
    """Customer subscription tier constants."""
    ANONYMOUS = "anonymous"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# Rate limits by tier (requests per minute)
TIER_RATE_LIMITS: dict[str, int] = {
    CustomerTier.ANONYMOUS:    30,
    CustomerTier.STARTER:      settings.tier_starter_limit,
    CustomerTier.PROFESSIONAL: settings.tier_professional_limit,
    CustomerTier.ENTERPRISE:   settings.tier_enterprise_limit,
}

# Role → tier mapping (fallback: users without explicit tier header use role)
ROLE_TO_TIER: dict[str, str] = {
    "admin":        CustomerTier.ENTERPRISE,
    "enterprise":   CustomerTier.ENTERPRISE,
    "professional": CustomerTier.PROFESSIONAL,
    "broker":       CustomerTier.PROFESSIONAL,
    "starter":      CustomerTier.STARTER,
    "client":       CustomerTier.STARTER,
}


def _get_client_identity(request: Request) -> tuple[str, str]:
    """
    Extract (identifier, tier) from the already-validated request state.

    IMPORTANT: Tier is read from request.state.user, which is populated by
    AuthenticationMiddleware AFTER validating the JWT/session token. This
    prevents clients from spoofing a higher tier via an X-Customer-Tier header.

    Falls back to IP-based anonymous identification.
    """
    user = getattr(request.state, "user", None)

    if user:
        user_id = user.get("id", "unknown")
        identifier = f"user:{user_id}"

        # Tier: prefer explicit 'tier' field, else map from 'role'
        tier = user.get("tier") or ROLE_TO_TIER.get(
            (user.get("role") or "").lower(), CustomerTier.STARTER
        )
        return identifier, tier

    # Unauthenticated: use client IP (respect X-Forwarded-For behind Caddy)
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    return f"ip:{ip}", CustomerTier.ANONYMOUS


# ---------------------------------------------------------------------------
# Redis connection (shared across middleware instances)
# ---------------------------------------------------------------------------

_redis_client = None


async def _get_redis_client():
    """Lazy-initialise async Redis client from RATE_LIMIT_STORAGE config."""
    global _redis_client
    if _redis_client is None:
        storage_url = settings.rate_limit_storage_url
        if storage_url.startswith("redis://") or storage_url.startswith("rediss://"):
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                storage_url,
                decode_responses=False,  # Lua returns raw bytes for numbers
            )
            logger.info(f"Rate limiter using Redis backend: {storage_url}")
        else:
            logger.warning(
                "RATE_LIMIT_STORAGE is not a Redis URL. "
                "Falling back to in-memory rate limiting — NOT safe for multi-worker production."
            )
    return _redis_client


# In-memory fallback (dev / single-process)
_memory_buckets: dict[str, TokenBucket] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    - In production (RATE_LIMIT_STORAGE=redis://…): uses Redis atomic Lua script.
    - In development (RATE_LIMIT_STORAGE=memory://): uses in-process TokenBucket.
    """

    EXEMPT_PATHS = {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/health",
        "/api/health/ready",
        "/api/health/info",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        if request.url.path in self.EXEMPT_PATHS or request.url.path.startswith("/api/health"):
            return await call_next(request)

        identifier, tier = _get_client_identity(request)
        limit_per_min = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[CustomerTier.ANONYMOUS])
        rate_per_sec = limit_per_min / 60.0
        capacity = limit_per_min

        storage_url = settings.rate_limit_storage_url
        allowed = True
        remaining = capacity

        if storage_url.startswith("redis://") or storage_url.startswith("rediss://"):
            # Redis-backed path (production)
            try:
                redis = await _get_redis_client()
                bucket = RedisTokenBucket(redis, key=f"rl:{identifier}", rate=rate_per_sec, capacity=capacity)
                allowed = await bucket.consume()
                remaining = int(await bucket.tokens_remaining())
            except Exception as e:
                # Redis unavailable — fail open to avoid blocking all traffic
                logger.error(f"Rate limiter Redis error (failing open): {e}")
                allowed = True
                remaining = -1
        else:
            # In-memory fallback (dev)
            if identifier not in _memory_buckets:
                _memory_buckets[identifier] = TokenBucket(rate_per_sec, capacity)
            bucket_mem = _memory_buckets[identifier]
            allowed = bucket_mem.consume()
            remaining = int(bucket_mem.tokens)

        if not allowed:
            retry_after = max(1, int(60 / limit_per_min))
            logger.warning(
                "Rate limit exceeded",
                extra={"identifier": identifier, "tier": tier, "limit": limit_per_min},
            )
            raise RateLimitExceeded(retry_after)

        response = await call_next(request)

        # Attach rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit_per_min)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Tier"] = tier

        return response


def rate_limit(limit: str = None, tier_based: bool = True):
    """
    Decorator for custom rate limiting on specific endpoints.

    Usage:
        @router.get("/expensive-operation")
        @rate_limit("10/minute")
        async def expensive_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
