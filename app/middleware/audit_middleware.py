"""Middleware for audit logging of all API requests."""

import json
import time
from collections.abc import Callable

from fastapi import Request, Response
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

from app.db.database import engine
from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests to database."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log to database."""

        # Skip logging for certain paths
        if self._should_skip_logging(request.url.path):
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Extract user information from headers
        user_email = request.headers.get("x-user")
        action = request.headers.get("x-action")

        # Get API key info by parsing the header directly
        api_key_id = None
        api_key_name = None
        api_key_header = request.headers.get("x-api-key")
        if api_key_header:
            api_key_info = self._get_api_key_info(api_key_header)
            if api_key_info:
                api_key_id = api_key_info["id"]
                api_key_name = api_key_info["name"]

        # Extract query parameters
        query_params = dict(request.query_params) if request.query_params else None

        # Get client IP
        ip_address = self._get_client_ip(request)

        # Process request and capture response
        response = None
        error_message = None
        status_code = None
        response_body = b""

        async def capture_response_body(message: Message) -> None:
            """Capture response body for error logging."""
            nonlocal response_body
            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    response_body += body

        try:
            response = await call_next(request)
            status_code = response.status_code

            # For error responses, try to capture the body
            if status_code >= 400:
                # Read response body if available
                if hasattr(response, "body"):
                    response_body = response.body

                # Extract error message from body
                error_message = self._extract_error_from_body(response_body, status_code)

        except Exception as e:
            status_code = 500
            error_message = f"{type(e).__name__}: {str(e)}"
            raise
        finally:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log to database
            self._log_to_database(
                user_email=user_email,
                action=action,
                method=request.method,
                path=request.url.path,
                query_params=query_params,
                api_key_id=api_key_id,
                api_key_name=api_key_name,
                status_code=status_code,
                duration_ms=duration_ms,
                ip_address=ip_address,
                user_agent=request.headers.get("user-agent"),
                error_message=error_message,
            )

        return response

    def _should_skip_logging(self, path: str) -> bool:
        """Determine if path should skip logging."""
        # Skip health checks and docs
        skip_paths = ["/health", "/", "/docs", "/redoc", "/openapi.json"]
        return path in skip_paths

    def _extract_error_from_body(self, body: bytes, status_code: int) -> str:
        """
        Extract error message from response body.

        FastAPI returns errors in JSON format like:
        {"detail": "Error message here"}
        or for validation errors:
        {"detail": [{"loc": [...], "msg": "...", "type": "..."}]}
        """
        if not body:
            return f"HTTP {status_code} error"

        try:
            # Try to parse body as JSON
            body_str = body.decode("utf-8")
            body_json = json.loads(body_str)

            # Extract 'detail' field (FastAPI's standard error format)
            if isinstance(body_json, dict) and "detail" in body_json:
                detail = body_json["detail"]

                # Handle string detail (most common)
                if isinstance(detail, str):
                    return detail

                # Handle list detail (validation errors)
                elif isinstance(detail, list):
                    # Extract first error message
                    if detail and isinstance(detail[0], dict):
                        msg = detail[0].get("msg", "Validation error")
                        loc = detail[0].get("loc", [])
                        if loc:
                            field = " -> ".join(str(x) for x in loc)
                            return f"{msg} (field: {field})"
                        return msg
                    return "Validation error"

                # Handle other types
                else:
                    return str(detail)

            # If no detail field, return generic message
            return f"HTTP {status_code} error"

        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            # If we can't parse the body, return generic message
            return f"HTTP {status_code} error"

    def _get_api_key_info(self, api_key: str) -> dict | None:
        """
        Get API key ID and name from the key string.

        This duplicates some logic from AuthService but is necessary
        because middleware runs before dependencies.
        """
        try:
            import hashlib

            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            with Session(engine) as session:
                statement = select(ApiKey).where(
                    ApiKey.key_hash == key_hash,
                    ApiKey.is_active == True,  # noqa: E712
                )
                api_key_obj = session.exec(statement).first()

                if api_key_obj:
                    return {
                        "id": api_key_obj.id,
                        "name": api_key_obj.name,
                    }
        except Exception:
            # If we can't get API key info, just skip it
            # Don't fail the request due to logging issues
            pass

        return None

    def _get_client_ip(self, request: Request) -> str | None:
        """Extract client IP address from request."""
        # Check X-Forwarded-For header (for proxy/load balancer)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client
        if request.client:
            return request.client.host

        return None

    def _log_to_database(
        self,
        user_email: str | None,
        action: str | None,
        method: str,
        path: str,
        query_params: dict | None,
        api_key_id: int | None,
        api_key_name: str | None,
        status_code: int | None,
        duration_ms: float,
        ip_address: str | None,
        user_agent: str | None,
        error_message: str | None,
    ) -> None:
        """Log request to database."""
        try:
            with Session(engine) as session:
                audit_entry = AuditLog(
                    user_email=user_email,
                    action=action,
                    method=method,
                    path=path,
                    query_params=query_params,
                    api_key_id=api_key_id,
                    api_key_name=api_key_name,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=error_message,
                )

                session.add(audit_entry)
                session.commit()
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to write audit log: {e}")
