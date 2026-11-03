"""TRD §16.6 + §7.6 envelope kesalahan. ERR-01/02: nasabah hanya terima customer_message_id."""
from typing import Any, Optional
from pydantic import BaseModel

ERROR_TO_HTTP = {
    "E_VALIDATION": 400, "E_UNAUTHORISED": 401, "E_ASSURANCE_REQUIRED": 422,
    "E_APPROVAL_REQUIRED": 422, "E_APPROVAL_ARGS_MISMATCH": 409,
    "E_NOT_FOUND": 404, "E_CONFLICT": 409, "E_RATE_LIMIT": 429,
    "E_TIMEOUT": 504, "E_UPSTREAM": 502, "E_UNAVAILABLE": 503,
    "E_INVALID_TRANSITION": 409, "E_PROHIBITED": 403,
}

class AppError(Exception):
    def __init__(self, error_code: str, message: str, customer_message_id: str | None = None,
                 correlation_id: str | None = None, retryable: bool = False,
                 details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.customer_message_id = customer_message_id
        self.correlation_id = correlation_id
        self.retryable = retryable
        self.details = details or []

    def envelope(self) -> dict[str, Any]:
        return {"error_code": self.error_code, "message": self.message,
                "customer_message_id": self.customer_message_id,
                "correlation_id": self.correlation_id, "retryable": self.retryable,
                "details": self.details}

    @property
    def http_status(self) -> int:
        return ERROR_TO_HTTP.get(self.error_code, 500)
