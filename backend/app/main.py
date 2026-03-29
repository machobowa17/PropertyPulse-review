import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger("uvicorn.error")

from app.routers import resolve, area, commute, report

# ---------------------------------------------------------------------------
# Rate limiter — 60 requests/minute per IP on all endpoints
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="UK Property Portal API",
    version="0.3.0",
    # Hide docs in production via env if needed; keep enabled for now
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ---------------------------------------------------------------------------
# GZip compression
# ---------------------------------------------------------------------------
app.add_middleware(GZipMiddleware, minimum_size=500)

# ---------------------------------------------------------------------------
# CORS — allow frontend origins only
# In production set ALLOWED_ORIGINS env var to your actual domain(s)
# ---------------------------------------------------------------------------
import os
_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3001,http://localhost:5173,http://localhost:8008")
ALLOWED_ORIGINS = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Accept-Encoding", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "script-src 'none'; "
        "style-src 'none'; "
        "frame-ancestors 'none';"
    )
    # Remove server fingerprint
    if "server" in response.headers:
        del response.headers["server"]
    return response

# ---------------------------------------------------------------------------
# Global exception handler — never leak tracebacks to clients
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(resolve.router, prefix="/api/v1")
app.include_router(area.router, prefix="/api/v1")
app.include_router(commute.router, prefix="/api/v1")
app.include_router(report.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
