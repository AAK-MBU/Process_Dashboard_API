"""API endpoints for viewing audit logs."""

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import paginate
from sqlmodel import select

from app.api.dependencies import RequireAdminKey
from app.core.pagination import add_pagination_links
from app.db.database import SessionDep
from app.models.audit_log import AuditLog, AuditLogPublic

router = APIRouter()


@router.get(
    "/",
    response_model=Page[AuditLogPublic],
    summary="List audit logs",
    description="Retrieve audit logs with filtering (admin only)",
)
def list_audit_logs(
    request: Request,
    response: Response,
    session: SessionDep,
    admin_key: RequireAdminKey,
    # Filters
    user_email: str | None = Query(None, description="Filter by user email"),
    action: str | None = Query(None, description="Filter by action"),
    method: str | None = Query(None, description="Filter by HTTP method"),
    path: str | None = Query(None, description="Filter by path (partial match)"),
    status_code: int | None = Query(None, description="Filter by status code"),
    min_duration: float | None = Query(None, description="Minimum duration in ms"),
    # Pagination
    params: Params = Depends(),
) -> Page[AuditLog]:
    """List audit logs with optional filtering."""
    statement = select(AuditLog)

    # Apply filters
    if user_email:
        statement = statement.where(AuditLog.user_email == user_email)
    if action:
        statement = statement.where(AuditLog.action == action)
    if method:
        statement = statement.where(AuditLog.method == method)
    if path:
        statement = statement.where(AuditLog.path.contains(path))
    if status_code:
        statement = statement.where(AuditLog.status_code == status_code)
    if min_duration:
        statement = statement.where(AuditLog.duration_ms >= min_duration)

    # Order by newest first
    statement = statement.order_by(AuditLog.created_at.desc())

    # Paginate
    page_data = paginate(session, statement, params)
    add_pagination_links(request, response, page_data)

    return page_data


@router.get(
    "/users",
    response_model=list[str],
    summary="List unique users",
    description="Get list of unique user emails from audit logs (admin only)",
)
def list_audit_users(
    session: SessionDep,
    admin_key: RequireAdminKey,
) -> list[str]:
    """Get list of unique users who have made requests."""
    statement = select(AuditLog.user_email).distinct().where(AuditLog.user_email.is_not(None))
    users = session.exec(statement).all()
    return sorted([u for u in users if u])


@router.get(
    "/actions",
    response_model=list[str],
    summary="List unique actions",
    description="Get list of unique actions from audit logs (admin only)",
)
def list_audit_actions(
    session: SessionDep,
    admin_key: RequireAdminKey,
) -> list[str]:
    """Get list of unique actions that have been performed."""
    statement = select(AuditLog.action).distinct().where(AuditLog.action.is_not(None))
    actions = session.exec(statement).all()
    return sorted([a for a in actions if a])


@router.get(
    "/stats",
    summary="Get audit log statistics",
    description="Get statistics about API usage (admin only)",
)
def get_audit_stats(
    session: SessionDep,
    admin_key: RequireAdminKey,
    user_email: str | None = Query(None, description="Filter stats by user"),
    hours: int = Query(24, description="Stats for last N hours"),
) -> dict:
    """Get statistics about API usage."""
    from datetime import timedelta

    from sqlmodel import func

    from app.utils.datetime_utils import utc_now

    # Calculate time threshold
    time_threshold = utc_now() - timedelta(hours=hours)

    # Base query
    statement = select(AuditLog).where(AuditLog.created_at >= time_threshold)
    if user_email:
        statement = statement.where(AuditLog.user_email == user_email)

    logs = session.exec(statement).all()

    if not logs:
        return {
            "total_requests": 0,
            "period_hours": hours,
            "user_filter": user_email,
        }

    # Calculate statistics
    total = len(logs)
    successful = sum(1 for log in logs if log.status_code and 200 <= log.status_code < 300)
    errors = sum(1 for log in logs if log.status_code and log.status_code >= 400)

    durations = [log.duration_ms for log in logs if log.duration_ms]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Count by method
    methods = {}
    for log in logs:
        methods[log.method] = methods.get(log.method, 0) + 1

    # Count by action
    actions = {}
    for log in logs:
        if log.action:
            actions[log.action] = actions.get(log.action, 0) + 1

    # Top users
    user_counts = {}
    for log in logs:
        if log.user_email:
            user_counts[log.user_email] = user_counts.get(log.user_email, 0) + 1
    top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_requests": total,
        "successful_requests": successful,
        "error_requests": errors,
        "success_rate": round(successful / total * 100, 2) if total > 0 else 0,
        "average_duration_ms": round(avg_duration, 2),
        "requests_by_method": methods,
        "requests_by_action": actions,
        "top_users": [{"email": email, "count": count} for email, count in top_users],
        "period_hours": hours,
        "user_filter": user_email,
    }
