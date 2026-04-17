"""Shared rate limiter instance — imported by main.py and routers for per-endpoint limits.

Uses Redis as the storage backend so rate limits are shared across Uvicorn workers.
Falls back to in-memory if Redis is unavailable (dev/test).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT],
    storage_uri=settings.REDIS_URL,
)
