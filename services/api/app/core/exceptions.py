"""
GATE Platform — Domain Exception Hierarchy.

All domain-specific exceptions inherit from GateError.
FastAPI exception handlers in main.py map these to HTTP responses.
"""
from typing import Any, Optional, Dict


class GateError(Exception):
    """Base exception for all GATE platform errors."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        result = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


class NotFoundError(GateError):
    """Resource not found (404)."""

    code = "NOT_FOUND"
    status_code = 404

    def __init__(self, resource: str, identifier: Any = None):
        details = {"resource": resource}
        if identifier is not None:
            details["id"] = str(identifier)
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(message, details)


class ValidationError(GateError):
    """Request validation failed (422)."""

    code = "VALIDATION_ERROR"
    status_code = 422

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        _details = details or {}
        if field:
            _details["field"] = field
        super().__init__(message, _details)


class AuthenticationError(GateError):
    """Authentication required or failed (401)."""

    code = "AUTHENTICATION_REQUIRED"
    status_code = 401

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message)


class AuthorizationError(GateError):
    """Insufficient permissions (403)."""

    code = "FORBIDDEN"
    status_code = 403

    def __init__(self, message: str = "Insufficient permissions", required: Optional[str] = None):
        details = {}
        if required:
            details["required"] = required
        super().__init__(message, details)


class ConflictError(GateError):
    """Resource conflict (409) — duplicate, already exists, etc."""

    code = "CONFLICT"
    status_code = 409

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class RateLimitError(GateError):
    """Rate limit exceeded (429)."""

    code = "RATE_LIMITED"
    status_code = 429

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, details)


class ServiceError(GateError):
    """External service failure (502)."""

    code = "SERVICE_UNAVAILABLE"
    status_code = 502

    def __init__(self, service: str, message: str = "Service unavailable"):
        super().__init__(message, {"service": service})
