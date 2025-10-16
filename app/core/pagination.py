"""Custom pagination utilities for adding Link headers."""

from typing import Any
from urllib.parse import urlencode

from fastapi import Request, Response
from fastapi_pagination import Page
from starlette.middleware.base import BaseHTTPMiddleware


def add_pagination_links(request: Request, response: Response, page_data: Page[Any]) -> None:
    """
    Add RFC 8288 compliant Link headers for pagination.

    Args:
        request: The FastAPI request object
        response: The FastAPI response object
        page_data: The paginated response data
    """
    if not isinstance(page_data, Page):
        return

    base_url = str(request.url).split("?")[0]
    query_params = dict(request.query_params)

    links = []

    # First page
    first_params = {**query_params, "page": 1, "size": page_data.size}
    links.append(f'<{base_url}?{urlencode(first_params)}>; rel="first"')

    # Last page
    last_params = {**query_params, "page": page_data.pages, "size": page_data.size}
    links.append(f'<{base_url}?{urlencode(last_params)}>; rel="last"')

    # Previous page (if not on first page)
    if page_data.page > 1:
        prev_params = {**query_params, "page": page_data.page - 1, "size": page_data.size}
        links.append(f'<{base_url}?{urlencode(prev_params)}>; rel="prev"')

    # Next page (if not on last page)
    if page_data.page < page_data.pages:
        next_params = {**query_params, "page": page_data.page + 1, "size": page_data.size}
        links.append(f'<{base_url}?{urlencode(next_params)}>; rel="next"')

    # Add Link header
    if links:
        response.headers["Link"] = ", ".join(links)

    # Add custom pagination headers for convenience
    response.headers["X-Total-Count"] = str(page_data.total)
    response.headers["X-Page"] = str(page_data.page)
    response.headers["X-Page-Size"] = str(page_data.size)
    response.headers["X-Total-Pages"] = str(page_data.pages)


class PaginationHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically add pagination Link headers to responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # The Link headers are added in the endpoint itself for better control
        # This middleware can be extended for global pagination header logic if needed

        return response
