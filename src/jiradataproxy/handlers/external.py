"""Handlers for the app's external API, ``/jira-data-proxy/``."""

from urllib.parse import urlencode, urljoin

from fastapi import APIRouter, Depends, Request, Response
from httpx import AsyncClient
from safir.dependencies.http_client import http_client_dependency
from safir.dependencies.logger import logger_dependency
from structlog.stdlib import BoundLogger

from ..config import config

__all__ = ["get_jira", "external_router"]

external_router = APIRouter()
"""FastAPI router for all external handlers."""


@external_router.get(
    "/{path:path}",
    description="Proxy GET requests to Jira.",
    name="proxy",
    response_model=None,
)
async def get_jira(
    path: str,
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    http_client: AsyncClient = Depends(http_client_dependency),
) -> Response:
    """Proxy GET requests to Jira."""
    # Format the Jira URL. The Configuration model validates that jira_base_url
    # ends with a trailing slash. And path does not start with a slash, so the
    # paths can be concatenated.
    base_url = str(config.jira_base_url)
    if not base_url.endswith("/"):
        base_url += "/"
    url = urljoin(base_url, path, allow_fragments=False)
    if request.query_params:
        qs = urlencode(dict(request.query_params.items()))
        url = f"{url}?{qs}"

    logger.debug(
        "Got Jira request",
        path=path,
        jira_url=url,
    )

    new_headers = {
        "Accept": "application/json",
    }
    r = await http_client.get(
        url,
        auth=(config.jira_username, config.jira_password.get_secret_value()),
        headers=new_headers,
    )

    pass_headers = ["content-type"]
    response_headers = {
        k: v for k, v in r.headers.items() if k.lower() in pass_headers
    }
    return Response(
        r.text, headers=response_headers, status_code=r.status_code
    )
