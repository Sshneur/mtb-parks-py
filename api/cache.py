import time
from typing import Optional

_cache: dict[str, dict] = {}

CACHE_TTL = 120  # 2 минуты
MAX_CACHE_KEYS = 200

def get_cached(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < entry["ttl"]:
        return entry["data"]
    if entry:
        del _cache[key]
    return None

def set_cached(key: str, data: dict, ttl: int = CACHE_TTL):
    if key not in _cache and len(_cache) >= MAX_CACHE_KEYS:
        oldest_key = min(_cache, key=lambda k: _cache[k]["ts"])
        del _cache[oldest_key]
    _cache[key] = {"data": data, "ts": time.time(), "ttl": ttl}

def invalidate_cache():
    _cache.clear()