"""FR-SEC-005 propagasi correlation ID. ID-6: dibangkitkan di edge bila tidak ada."""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from .ids import new_id

class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or new_id("correlation")
        request.state.correlation_id = cid
        resp = await call_next(request)
        resp.headers["X-Correlation-Id"] = cid
        return resp
