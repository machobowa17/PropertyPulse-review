"""Redis caching layer — graceful degradation if Redis is unavailable."""
import json
import logging
import redis.asyncio as aioredis
from app.config import settings

log = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    global _pool
    if _pool is None:
        try:
            _pool = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1
            )
            await _pool.ping()
        except Exception as exc:
            log.warning("Redis connection failed: %s", exc)
            _pool = None
    return _pool


async def cache_get(key: str):
    r = await get_redis()
    if not r:
        return None
    try:
        val = await r.get(key)
        return json.loads(val) if val else None
    except Exception as exc:
        log.warning("cache_get(%s) failed: %s", key, exc)
        return None


async def cache_set(key: str, value, ttl: int = 3600):
    r = await get_redis()
    if not r:
        return
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        log.warning("cache_set(%s) failed: %s", key, exc)
