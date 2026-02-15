"""
Rate Limiting Middleware with Customer Tier Support.

Provides tiered rate limiting based on customer subscription level:
- Starter: 60 requests/minute
- Professional: 200 requests/minute
- Enterprise: 1000 requests/minute

Also includes IP-based rate limiting for unauthenticated requests.
"""
from typing import Optional, Callable
from datetime import datetime, timedelta
import time
import logging
from collections import defaultdict
from functools import wraps

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
    Token bucket rate limiter.
    
    Allows burst traffic while maintaining average rate limit.
    """
    
    def __init__(self, rate: int, capacity: int):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Returns True if tokens were consumed, False if rate limited.
        """
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        
        # Add tokens based on time elapsed
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def time_until_available(self) -> float:
        """Return seconds until a token will be available."""
        if self.tokens >= 1:
            return 0
        return (1 - self.tokens) / self.rate


class CustomerTier:
    """Customer subscription tier."""
    ANONYMOUS = "anonymous"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# Rate limits by tier (requests per minute)
TIER_RATE_LIMITS = {
    CustomerTier.ANONYMOUS: 30,  # IP-based, generous for demos
    CustomerTier.STARTER: settings.tier_starter_limit,
    CustomerTier.PROFESSIONAL: settings.tier_professional_limit,
    CustomerTier.ENTERPRISE: settings.tier_enterprise_limit,
}


class RateLimiter:
    """
    Rate limiter with customer tier support.
    
    Uses in-memory storage by default. For production with multiple
    instances, use Redis storage.
    """
    
    def __init__(self):
        # Buckets keyed by identifier (IP or customer_id)
        self.buckets: dict[str, TokenBucket] = {}
        # Customer tier cache (customer_id -> tier)
        self.tier_cache: dict[str, tuple[str, datetime]] = {}
        self.tier_cache_ttl = timedelta(minutes=5)
    
    def _get_bucket(self, identifier: str, tier: str) -> TokenBucket:
        """Get or create token bucket for identifier."""
        if identifier not in self.buckets:
            limit = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[CustomerTier.ANONYMOUS])
            # Convert per-minute to per-second rate
            rate = limit / 60
            capacity = limit  # Allow burst up to full minute limit
            self.buckets[identifier] = TokenBucket(rate, capacity)
        return self.buckets[identifier]
    
    def _get_client_tier(self, request: Request) -> tuple[str, str]:
        """
        Extract client identifier and tier from request.
        
        Returns (identifier, tier) tuple.
        """
        # Try to get customer ID from JWT token
        customer_id = None
        tier = CustomerTier.ANONYMOUS
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # In a real implementation, decode JWT and get customer info
            # For now, check for tier header or use default
            # TODO: Integrate with actual auth service
            customer_id = request.headers.get("X-Customer-ID")
            tier_header = request.headers.get("X-Customer-Tier", "").lower()
            
            if tier_header in TIER_RATE_LIMITS:
                tier = tier_header
            elif customer_id:
                # Default authenticated users to starter
                tier = CustomerTier.STARTER
        
        # Use customer ID if authenticated, else use IP
        if customer_id:
            identifier = f"customer:{customer_id}"
        else:
            # Use forwarded IP if behind proxy, else direct IP
            forwarded = request.headers.get("X-Forwarded-For", "")
            if forwarded:
                identifier = f"ip:{forwarded.split(',')[0].strip()}"
            else:
                identifier = f"ip:{request.client.host if request.client else 'unknown'}"
        
        return identifier, tier
    
    def check_rate_limit(self, request: Request) -> tuple[bool, int]:
        """
        Check if request is rate limited.
        
        Returns (allowed, retry_after_seconds) tuple.
        """
        identifier, tier = self._get_client_tier(request)
        bucket = self._get_bucket(identifier, tier)
        
        if bucket.consume():
            return True, 0
        
        retry_after = int(bucket.time_until_available()) + 1
        logger.warning(
            f"Rate limit exceeded for {identifier} (tier: {tier})",
            extra={
                "identifier": identifier,
                "tier": tier,
                "retry_after": retry_after,
            }
        )
        return False, retry_after
    
    def get_rate_info(self, request: Request) -> dict:
        """Get rate limit info for response headers."""
        identifier, tier = self._get_client_tier(request)
        bucket = self._get_bucket(identifier, tier)
        limit = TIER_RATE_LIMITS.get(tier, 30)
        
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(int(bucket.tokens)),
            "X-RateLimit-Tier": tier,
        }
    
    def cleanup_old_buckets(self, max_age_seconds: int = 3600):
        """Remove buckets that haven't been used recently."""
        now = time.time()
        to_remove = []
        
        for identifier, bucket in self.buckets.items():
            if now - bucket.last_update > max_age_seconds:
                to_remove.append(identifier)
        
        for identifier in to_remove:
            del self.buckets[identifier]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} stale rate limit buckets")


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Applies rate limits based on customer tier and adds rate limit
    headers to all responses.
    """
    
    # Paths exempt from rate limiting
    EXEMPT_PATHS = {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/health",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip if rate limiting disabled
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Check rate limit
        allowed, retry_after = rate_limiter.check_rate_limit(request)
        
        if not allowed:
            raise RateLimitExceeded(retry_after)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        rate_info = rate_limiter.get_rate_info(request)
        for header, value in rate_info.items():
            response.headers[header] = value
        
        return response


def rate_limit(limit: str = None, tier_based: bool = True):
    """
    Decorator for custom rate limiting on specific endpoints.
    
    Usage:
        @router.get("/expensive-operation")
        @rate_limit("10/minute")
        async def expensive_operation():
            ...
    
    Args:
        limit: Rate limit string (e.g., "10/minute", "100/hour")
        tier_based: If True, multiply limit by tier multiplier
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Custom rate limiting logic can be added here
            # For now, rely on middleware
            return await func(*args, **kwargs)
        return wrapper
    return decorator
