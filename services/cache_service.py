"""Advanced caching service with Redis backend and intelligent cache management."""

import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Union
import structlog
from functools import wraps
import redis.asyncio as redis
from config import settings

logger = structlog.get_logger()

class CacheService:
    """Advanced caching service with Redis backend."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
        self.default_ttl = 3600  # 1 hour
        
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            if hasattr(settings, 'redis_url') and settings.redis_url:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                await self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            else:
                logger.info("Redis not configured, using local cache only")
        except Exception as e:
            logger.warning("Failed to connect to Redis, falling back to local cache", error=str(e))
            self.redis_client = None
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    value = await self.redis_client.get(key)
                    if value is not None:
                        self.cache_stats["hits"] += 1
                        return json.loads(value)
                except Exception as e:
                    logger.warning(f"Redis get failed for key {key}", error=str(e))
            
            # Fallback to local cache
            if key in self.local_cache:
                cache_entry = self.local_cache[key]
                if cache_entry["expires_at"] > datetime.utcnow():
                    self.cache_stats["hits"] += 1
                    return cache_entry["value"]
                else:
                    # Expired, remove from local cache
                    del self.local_cache[key]
            
            self.cache_stats["misses"] += 1
            return default
            
        except Exception as e:
            logger.error(f"Cache get failed for key {key}", error=str(e))
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value, default=str)
            
            # Try Redis first
            if self.redis_client:
                try:
                    await self.redis_client.setex(key, ttl, serialized_value)
                    self.cache_stats["sets"] += 1
                    return True
                except Exception as e:
                    logger.warning(f"Redis set failed for key {key}", error=str(e))
            
            # Fallback to local cache
            self.local_cache[key] = {
                "value": value,
                "expires_at": datetime.utcnow() + timedelta(seconds=ttl)
            }
            self.cache_stats["sets"] += 1
            
            # Clean up expired local cache entries periodically
            if len(self.local_cache) % 100 == 0:
                await self._cleanup_local_cache()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed for key {key}", error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            deleted = False
            
            # Try Redis first
            if self.redis_client:
                try:
                    result = await self.redis_client.delete(key)
                    deleted = result > 0
                except Exception as e:
                    logger.warning(f"Redis delete failed for key {key}", error=str(e))
            
            # Also remove from local cache
            if key in self.local_cache:
                del self.local_cache[key]
                deleted = True
            
            if deleted:
                self.cache_stats["deletes"] += 1
            
            return deleted
            
        except Exception as e:
            logger.error(f"Cache delete failed for key {key}", error=str(e))
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            deleted_count = 0
            
            # Try Redis first
            if self.redis_client:
                try:
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        deleted_count = await self.redis_client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Redis pattern delete failed for pattern {pattern}", error=str(e))
            
            # Also clean local cache
            keys_to_delete = [key for key in self.local_cache.keys() if self._match_pattern(key, pattern)]
            for key in keys_to_delete:
                del self.local_cache[key]
                deleted_count += 1
            
            self.cache_stats["deletes"] += deleted_count
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache pattern delete failed for pattern {pattern}", error=str(e))
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    return await self.redis_client.exists(key) > 0
                except Exception as e:
                    logger.warning(f"Redis exists check failed for key {key}", error=str(e))
            
            # Check local cache
            if key in self.local_cache:
                cache_entry = self.local_cache[key]
                if cache_entry["expires_at"] > datetime.utcnow():
                    return True
                else:
                    del self.local_cache[key]
            
            return False
            
        except Exception as e:
            logger.error(f"Cache exists check failed for key {key}", error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a numeric value in cache."""
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    return await self.redis_client.incrby(key, amount)
                except Exception as e:
                    logger.warning(f"Redis increment failed for key {key}", error=str(e))
            
            # Fallback to local cache
            current_value = await self.get(key, 0)
            new_value = int(current_value) + amount
            await self.set(key, new_value)
            return new_value
            
        except Exception as e:
            logger.error(f"Cache increment failed for key {key}", error=str(e))
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = dict(self.cache_stats)
        stats["local_cache_size"] = len(self.local_cache)
        stats["hit_rate"] = (
            stats["hits"] / (stats["hits"] + stats["misses"]) * 100
            if (stats["hits"] + stats["misses"]) > 0 else 0
        )
        
        if self.redis_client:
            try:
                redis_info = await self.redis_client.info("memory")
                stats["redis_memory_used"] = redis_info.get("used_memory_human", "N/A")
                stats["redis_connected"] = True
            except Exception:
                stats["redis_connected"] = False
        else:
            stats["redis_connected"] = False
        
        return stats
    
    async def _cleanup_local_cache(self):
        """Clean up expired entries from local cache."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.local_cache.items()
            if entry["expires_at"] <= now
        ]
        
        for key in expired_keys:
            del self.local_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for cache keys."""
        if "*" not in pattern:
            return key == pattern
        
        # Convert glob pattern to regex-like matching
        pattern_parts = pattern.split("*")
        if len(pattern_parts) == 2:
            prefix, suffix = pattern_parts
            return key.startswith(prefix) and key.endswith(suffix)
        
        return False


def cache_result(ttl: int = 3600, key_prefix: str = ""):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:"
            
            # Create a hash of arguments for the key
            args_str = str(args) + str(sorted(kwargs.items()))
            args_hash = hashlib.md5(args_str.encode()).hexdigest()
            cache_key += args_hash
            
            # Try to get from cache
            cached_result = await cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_service.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# Global cache service instance
cache_service = CacheService()
