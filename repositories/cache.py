"""
Simple in-memory cache for RPC calls
Prevents flooding RabbitMQ with duplicate requests
"""
import time
import hashlib
import json
from typing import Optional, Dict, Any

# In-memory cache storage
_cache: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5 minutes


def _cache_key(pattern: str, payload: dict) -> str:
    """Generate cache key from pattern and payload"""
    key_str = f"{pattern}:{json.dumps(payload, sort_keys=True)}"
    return hashlib.md5(key_str.encode()).hexdigest()


def get_cached(pattern: str, payload: dict) -> Optional[Dict[str, Any]]:
    """Get cached RPC response if not expired"""
    key = _cache_key(pattern, payload)
    
    if key in _cache:
        cached_data, timestamp = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            print(f"✅ Cache HIT for {pattern}")
            return cached_data
        else:
            # Expired, remove from cache
            del _cache[key]
            print(f"🗑️ Cache EXPIRED for {pattern}")
    
    return None


def set_cached(pattern: str, payload: dict, response: Dict[str, Any]):
    """Cache RPC response with timestamp"""
    key = _cache_key(pattern, payload)
    _cache[key] = (response, time.time())
    print(f"💾 Cached {pattern} (TTL: {CACHE_TTL}s)")


def clear_cache():
    """Clear all cached entries (for testing/admin)"""
    global _cache
    _cache = {}
    print("🧹 Cache cleared")
