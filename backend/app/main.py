import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger("uvicorn.error")

from app.config import settings
from app.rate_limit import limiter
from app.routers import resolve, area, commute, report, health, data_freshness

# ---------------------------------------------------------------------------
# Sentry APM — initialise before app creation so all errors are captured.
# Set SENTRY_DSN env var to enable; no-op if unset.
# ---------------------------------------------------------------------------
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,   # 10% of requests traced for performance monitoring
        send_default_pii=False,
    )
    logger.info("Sentry APM initialised")

# Rate limiter imported from app.rate_limit (shared so routers can use @limiter.exempt)

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
# GZip compression — handled by Nginx in production.
# Python-level gzip burns CPU and blocks the event loop; let the reverse proxy do it.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CORS — allow frontend origins only
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
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
    # X-XSS-Protection intentionally omitted — deprecated; modern browsers ignore it
    # and in some edge cases it can introduce XSS via selective-blocking attacks.
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # CSP is intentionally omitted here — this is a JSON API, not a page-serving endpoint.
    # The nginx layer (nginx.conf / nginx-ssl.conf) applies a full CSP to the frontend.
    # Remove server fingerprint
    if "server" in response.headers:
        del response.headers["server"]
    return response

# ---------------------------------------------------------------------------
# HTTP exception handler — returns {"error": code, "detail": message}
# Structured detail dict (from http_error()) is returned as-is;
# plain string detail is wrapped under "detail".
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        content = detail
    else:
        content = {"error": "HTTP_ERROR", "detail": str(detail) if detail else "An error occurred"}
    return JSONResponse(status_code=exc.status_code, content=content)

# ---------------------------------------------------------------------------
# Validation error handler — return 422 with field-level detail, not 500
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_ERROR", "detail": exc.errors()},
    )

# ---------------------------------------------------------------------------
# Global exception handler — never leak tracebacks to clients
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": "An unexpected error occurred"})

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(resolve.router,         prefix="/api/v1")
app.include_router(area.router,           prefix="/api/v1")
app.include_router(commute.router,        prefix="/api/v1")
app.include_router(report.router,         prefix="/api/v1")
app.include_router(health.router,         prefix="/api/v1")
app.include_router(data_freshness.router, prefix="/api/v1")
