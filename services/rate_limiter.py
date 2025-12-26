"""Advanced rate limiting service with multiple algorithms and Redis backend."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
import structlog
from functools import wraps
from fastapi import HTTPException, Request
from services.cache_service import cache_service

logger = structlog.get_logger()

class RateLimiter:
    """Advanced rate limiting with multiple algorithms."""
    
    def __init__(self):
        self.local_buckets: Dict[str, Dict[str, Any]] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    async def check_rate_limit(
        self, 
        key: str, 
        limit: int, 
        window_seconds: int, 
        algorithm: str = "sliding_window"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.
        
        Args:
            key: Unique identifier for the rate limit (e.g., IP address, user ID)
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds
            algorithm: Rate limiting algorithm ('sliding_window', 'token_bucket', 'fixed_window')
        
        Returns:
            Tuple of (is_allowed, metadata)
        """
        try:
            if algorithm == "sliding_window":
                return await self._sliding_window_check(key, limit, window_seconds)
            elif algorithm == "token_bucket":
                return await self._token_bucket_check(key, limit, window_seconds)
            elif algorithm == "fixed_window":
                return await self._fixed_window_check(key, limit, window_seconds)
            else:
                raise ValueError(f"Unknown algorithm: {algorithm}")
                
        except Exception as e:
            logger.error(f"Rate limit check failed for key {key}", error=str(e))
            # Fail open - allow request if rate limiting fails
            return True, {"error": str(e)}
    
    async def _sliding_window_check(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict[str, Any]]:
        """Sliding window rate limiting algorithm."""
        now = time.time()
        window_key = f"rate_limit:sliding:{key}"
        
        # Get current window data
        window_data = await cache_service.get(window_key, [])
        
        # Remove old entries outside the window
        cutoff_time = now - window_seconds
        window_data = [timestamp for timestamp in window_data if timestamp > cutoff_time]
        
        # Check if we can add a new request
        current_count = len(window_data)
        is_allowed = current_count < limit
        
        if is_allowed:
            # Add current timestamp
            window_data.append(now)
            await cache_service.set(window_key, window_data, window_seconds + 60)  # Extra TTL buffer
        
        # Calculate reset time (when oldest request will expire)
        reset_time = int(window_data[0] + window_seconds) if window_data else int(now + window_seconds)
        
        metadata = {
            "algorithm": "sliding_window",
            "limit": limit,
            "remaining": max(0, limit - current_count - (1 if is_allowed else 0)),
            "reset_time": reset_time,
            "window_seconds": window_seconds,
            "current_count": current_count
        }
        
        return is_allowed, metadata
    
    async def _token_bucket_check(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict[str, Any]]:
        """Token bucket rate limiting algorithm."""
        now = time.time()
        bucket_key = f"rate_limit:bucket:{key}"
        
        # Get current bucket state
        bucket_data = await cache_service.get(bucket_key, {
            "tokens": limit,
            "last_refill": now
        })
        
        # Calculate tokens to add based on time elapsed
        time_elapsed = now - bucket_data["last_refill"]
        refill_rate = limit / window_seconds  # tokens per second
        tokens_to_add = time_elapsed * refill_rate
        
        # Update token count (cap at limit)
        current_tokens = min(limit, bucket_data["tokens"] + tokens_to_add)
        
        # Check if we can consume a token
        is_allowed = current_tokens >= 1
        
        if is_allowed:
            current_tokens -= 1
        
        # Update bucket state
        bucket_data = {
            "tokens": current_tokens,
            "last_refill": now
        }
        await cache_service.set(bucket_key, bucket_data, window_seconds * 2)  # Longer TTL
        
        # Calculate when bucket will be full again
        time_to_full = (limit - current_tokens) / refill_rate if current_tokens < limit else 0
        reset_time = int(now + time_to_full)
        
        metadata = {
            "algorithm": "token_bucket",
            "limit": limit,
            "remaining": int(current_tokens),
            "reset_time": reset_time,
            "refill_rate": refill_rate,
            "tokens": current_tokens
        }
        
        return is_allowed, metadata
    
    async def _fixed_window_check(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict[str, Any]]:
        """Fixed window rate limiting algorithm."""
        now = time.time()
        window_start = int(now // window_seconds) * window_seconds
        window_key = f"rate_limit:fixed:{key}:{window_start}"
        
        # Get current count for this window
        current_count = await cache_service.get(window_key, 0)
        
        # Check if we can increment
        is_allowed = current_count < limit
        
        if is_allowed:
            # Increment counter
            new_count = await cache_service.increment(window_key, 1)
            # Set TTL for the window
            await cache_service.set(window_key, new_count, window_seconds + 60)
            current_count = new_count
        
        reset_time = window_start + window_seconds
        
        metadata = {
            "algorithm": "fixed_window",
            "limit": limit,
            "remaining": max(0, limit - current_count),
            "reset_time": int(reset_time),
            "window_start": int(window_start),
            "window_seconds": window_seconds,
            "current_count": current_count
        }
        
        return is_allowed, metadata
    
    async def get_rate_limit_info(self, key: str, algorithm: str = "sliding_window") -> Dict[str, Any]:
        """Get current rate limit information without consuming quota."""
        try:
            if algorithm == "sliding_window":
                window_key = f"rate_limit:sliding:{key}"
                window_data = await cache_service.get(window_key, [])
                return {
                    "algorithm": algorithm,
                    "current_count": len(window_data),
                    "requests": window_data
                }
            elif algorithm == "token_bucket":
                bucket_key = f"rate_limit:bucket:{key}"
                bucket_data = await cache_service.get(bucket_key, {})
                return {
                    "algorithm": algorithm,
                    "bucket_state": bucket_data
                }
            elif algorithm == "fixed_window":
                # This would need the window parameters to be meaningful
                return {
                    "algorithm": algorithm,
                    "message": "Need window parameters for fixed window info"
                }
            
        except Exception as e:
            logger.error(f"Failed to get rate limit info for key {key}", error=str(e))
            return {"error": str(e)}
    
    async def reset_rate_limit(self, key: str, algorithm: str = "sliding_window") -> bool:
        """Reset rate limit for a specific key."""
        try:
            if algorithm == "sliding_window":
                window_key = f"rate_limit:sliding:{key}"
                await cache_service.delete(window_key)
            elif algorithm == "token_bucket":
                bucket_key = f"rate_limit:bucket:{key}"
                await cache_service.delete(bucket_key)
            elif algorithm == "fixed_window":
                # Delete all fixed window entries for this key
                pattern = f"rate_limit:fixed:{key}:*"
                await cache_service.delete_pattern(pattern)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset rate limit for key {key}", error=str(e))
            return False
    
    def _cleanup_local_buckets(self):
        """Clean up expired local bucket entries."""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        expired_keys = []
        for key, bucket in self.local_buckets.items():
            if now - bucket.get("last_access", 0) > self.cleanup_interval:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.local_buckets[key]
        
        self.last_cleanup = now
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit buckets")


def rate_limit(
    limit: int, 
    window_seconds: int, 
    algorithm: str = "sliding_window",
    key_func: Optional[callable] = None,
    skip_successful_requests: bool = False
):
    """
    Decorator for rate limiting API endpoints.
    
    Args:
        limit: Maximum number of requests allowed
        window_seconds: Time window in seconds
        algorithm: Rate limiting algorithm to use
        key_func: Function to generate rate limit key (default: uses client IP)
        skip_successful_requests: If True, only count failed requests
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # If no request object found, skip rate limiting
                return await func(*args, **kwargs)
            
            # Generate rate limit key
            if key_func:
                rate_limit_key = key_func(request)
            else:
                # Default: use client IP
                client_ip = request.client.host if request.client else "unknown"
                rate_limit_key = f"ip:{client_ip}:{func.__name__}"
            
            # Check rate limit
            is_allowed, metadata = await rate_limiter.check_rate_limit(
                rate_limit_key, limit, window_seconds, algorithm
            )
            
            if not is_allowed:
                # Rate limit exceeded
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": str(metadata.get("remaining", 0)),
                        "X-RateLimit-Reset": str(metadata.get("reset_time", 0)),
                        "X-RateLimit-Algorithm": algorithm,
                        "Retry-After": str(max(1, metadata.get("reset_time", 0) - int(time.time())))
                    }
                )
            
            # Execute the function
            try:
                result = await func(*args, **kwargs)
                
                # Add rate limit headers to successful responses
                if hasattr(result, "headers"):
                    result.headers["X-RateLimit-Limit"] = str(limit)
                    result.headers["X-RateLimit-Remaining"] = str(metadata.get("remaining", 0))
                    result.headers["X-RateLimit-Reset"] = str(metadata.get("reset_time", 0))
                
                return result
                
            except Exception as e:
                # If skip_successful_requests is True and this is a client error,
                # we might want to not count it against the rate limit
                # For now, we'll count all requests
                raise e
        
        return wrapper
    return decorator


# Rate limiting configurations for different endpoint types
RATE_LIMIT_CONFIGS = {
    "auth": {"limit": 5, "window_seconds": 300, "algorithm": "sliding_window"},  # 5 per 5 minutes
    "api_read": {"limit": 100, "window_seconds": 60, "algorithm": "token_bucket"},  # 100 per minute
    "api_write": {"limit": 20, "window_seconds": 60, "algorithm": "sliding_window"},  # 20 per minute
    "admin": {"limit": 50, "window_seconds": 60, "algorithm": "sliding_window"},  # 50 per minute
    "public": {"limit": 1000, "window_seconds": 3600, "algorithm": "fixed_window"},  # 1000 per hour
}

# Global rate limiter instance
rate_limiter = RateLimiter()
