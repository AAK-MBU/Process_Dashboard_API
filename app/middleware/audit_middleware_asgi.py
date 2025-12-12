"""Middleware for audit logging with response body capture."""

import json
import time
import traceback

from fastapi import Request
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse

from app.db.database import engine
from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests with response body capture."""

    async def dispatch(self, request: Request, call_next):
        """Process request and log to database."""

        # Skip logging for certain paths
        if self._should_skip_logging(request.url.path):
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Extract request information
        user_email = request.headers.get("x-user")
        action = request.headers.get("x-action")

        # Get API key info
        api_key_id = None
        api_key_name = None
        api_key_header = request.headers.get("x-api-key")
        if api_key_header:
            api_key_info = self._get_api_key_info(api_key_header)
            if api_key_info:
                api_key_id = api_key_info["id"]
                api_key_name = api_key_info["name"]

        query_params = dict(request.query_params) if request.query_params else None
        ip_address = self._get_client_ip(request)

        # Process request
        response = None
        error_message = None
        status_code = None

        try:
            response = await call_next(request)
            status_code = response.status_code

            # For error responses, capture and extract error message
            if status_code >= 400:
                response_body = b""

                # Check if response has body_iterator (streaming response)
                if hasattr(response, "body_iterator"):
                    # This handles both StreamingResponse and _StreamingResponse
                    async for chunk in response.body_iterator:
                        response_body += chunk

                    # Extract error message
                    error_message = self._extract_error_from_body(response_body, status_code)

                    # Recreate response with captured body
                    response = Response(
                        content=response_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                elif hasattr(response, "body"):
                    # For regular Response objects with body attribute
                    response_body = response.body
                    error_message = self._extract_error_from_body(response_body, status_code)

        except Exception as e:
            # Capture exception details
            status_code = 500
            error_message = f"{type(e).__name__}: {str(e)}"

            print(f"Exception in request: {error_message}")
            traceback.print_exc()

            raise
        finally:
            # Always log
            duration_ms = (time.time() - start_time) * 1000

            try:
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
            except Exception as log_error:
                print(f"Failed to write audit log: {log_error}")
                traceback.print_exc()

        return response

    def _extract_error_from_body(self, body: bytes, status_code: int) -> str:
        """Extract error message from response body bytes."""
        if not body:
            return f"HTTP {status_code} error"

        try:
            body_str = body.decode("utf-8")
            body_json = json.loads(body_str)

            if isinstance(body_json, dict) and "detail" in body_json:
                detail = body_json["detail"]

                if isinstance(detail, str):
                    return detail
                elif isinstance(detail, list) and detail:
                    if isinstance(detail[0], dict):
                        msg = detail[0].get("msg", "Validation error")
                        loc = detail[0].get("loc", [])
                        if loc:
                            field = " -> ".join(str(x) for x in loc)
                            return f"{msg} (field: {field})"
                        return msg
                    return "Validation error"
                else:
                    return str(detail)
        except Exception:
            pass

        return f"HTTP {status_code} error"

    def _should_skip_logging(self, path: str) -> bool:
        """Determine if path should skip logging."""
        skip_paths = ["/health", "/", "/docs", "/redoc", "/openapi.json"]
        return path in skip_paths

    def _get_api_key_info(self, api_key: str) -> dict | None:
        """Get API key ID and name."""
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
                    return {"id": api_key_obj.id, "name": api_key_obj.name}
        except Exception:
            pass
        return None

    def _get_client_ip(self, request: Request) -> str | None:
        """Extract client IP address."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

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
                duration_ms=round(duration_ms, 2) if duration_ms else None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=error_message,
            )

            session.add(audit_entry)
            session.commit()
