"""
Standardised error responses for all API endpoints.

Usage:
    from app.errors import http_error

    raise http_error(404, "NOT_FOUND", "Session not found")
    raise http_error(410, "SESSION_EXPIRED", "Session expired — please search again")
    raise http_error(400, "INVALID_PARAM", "tab must be one of: ...")
    raise http_error(500, "INTERNAL_ERROR", "Internal server error")
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error envelope — never leaks tracebacks to clients."""
    error: str   # short machine-readable code, e.g. "SESSION_EXPIRED"
    detail: str  # human-readable message


def http_error(status_code: int, error: str, detail: str) -> HTTPException:
    """Return a FastAPI HTTPException with a structured JSON body.

    The global exception handler in main.py catches all unhandled Exception
    instances and returns a generic 500.  Use this helper for expected errors
    so the response body is consistent with ErrorResponse.

    Example::
        raise http_error(410, "SESSION_EXPIRED", "Session expired — please search again")
    """
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "detail": detail},
    )
