"""Simple TTL-based cache for frequently accessed data.

This module provides a thread-safe, time-to-live (TTL) based cache
for reducing redundant API calls and database queries.

Validates: Requirements 14.4
"""

import logging
import time
import threading
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with value and expiration time.
    
    Attributes:
        value: Cached value
        expires_at: Timestamp when this entry expires
        created_at: Timestamp when this entry was created
    """
    value: Any
    expires_at: float
    created_at: float


class TTLCache:
    """
    Thread-safe TTL (Time-To-Live) cache.
    
    This cache stores key-value pairs with automatic expiration.
    Expired entries are removed automatically on access or during
    periodic cleanup.
    
    Features:
    - Thread-safe operations
    - Automatic expiration based on TTL
    - Optional periodic cleanup of expired entries
    - Cache statistics (hits, misses, size)
    """
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Initialize the TTL cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes)
            max_size: Maximum number of entries in cache (default: 1000)
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }
        
        logger.info(
            f"Initialized TTLCache with default_ttl={default_ttl}s, "
            f"max_size={max_size}"
        )
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Returns None if the key doesn't exist or has expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            # Check if expired
            if time.time() > entry.expires_at:
                # Remove expired entry
                del self._cache[key]
                self._stats["misses"] += 1
                self._stats["expirations"] += 1
                logger.debug(f"Cache entry expired: {key}")
                return None
            
            self._stats["hits"] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a value in the cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default_ttl if not specified)
        """
        with self._lock:
            # Check if we need to evict entries
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()
            
            ttl_seconds = ttl if ttl is not None else self.default_ttl
            now = time.time()
            
            entry = CacheEntry(
                value=value,
                expires_at=now + ttl_seconds,
                created_at=now
            )
            
            self._cache[key] = entry
            logger.debug(f"Cached entry: {key} (ttl={ttl_seconds}s)")
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted, False if key didn't exist
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Deleted cache entry: {key}")
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared cache ({count} entries)")
    
    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get a value from cache, or compute and cache it if not present.
        
        This is useful for lazy loading with automatic caching.
        
        Args:
            key: Cache key
            factory: Function to call if value is not in cache
            ttl: Time-to-live in seconds (uses default_ttl if not specified)
            
        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        value = self.get(key)
        if value is not None:
            return value
        
        # Compute value
        value = factory()
        
        # Cache it
        self.set(key, value, ttl)
        
        return value
    
    def _evict_oldest(self) -> None:
        """Evict the oldest entry from the cache (LRU-like behavior)."""
        if not self._cache:
            return
        
        # Find oldest entry by created_at
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at
        )
        
        del self._cache[oldest_key]
        self._stats["evictions"] += 1
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if now > entry.expires_at
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self._stats["expirations"] += 1
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing:
                - hits: Number of cache hits
                - misses: Number of cache misses
                - hit_rate: Cache hit rate (0-1)
                - size: Current number of entries
                - evictions: Number of entries evicted due to size limit
                - expirations: Number of entries expired
        """
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                self._stats["hits"] / total_requests
                if total_requests > 0
                else 0.0
            )
            
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": round(hit_rate, 3),
                "size": len(self._cache),
                "evictions": self._stats["evictions"],
                "expirations": self._stats["expirations"],
            }
    
    def reset_stats(self) -> None:
        """Reset cache statistics to zero."""
        with self._lock:
            self._stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "expirations": 0,
            }
            logger.debug("Reset cache statistics")
