"""Database connection pool for the School API."""

import os
from psycopg2 import pool

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

_pool = None


def _parse_dsn(url: str) -> dict:
    from urllib.parse import urlparse
    p = urlparse(url)
    return {
        "dbname": p.path.lstrip("/"),
        "user": p.username,
        "password": p.password,
        "host": p.hostname,
        "port": p.port or 5432,
    }


def get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        params = _parse_dsn(DATABASE_URL)
        _pool = pool.ThreadedConnectionPool(minconn=2, maxconn=8, **params)
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    get_pool().putconn(conn)
