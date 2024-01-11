"""Handlers for the app's external API, ``/jira-data-proxy/``."""

from urllib.parse import urlencode

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
    # Format the Jira URL. Potentially this can be done entirely through the
    # urllib.parse module, but I'm not sure how to concatenate a path
    # with it.
    base_url = config.jira_base_url
    if not base_url.endswith("/"):
        base_url += "/"
    url = f"{config.jira_base_url}{path}"
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

    response_headers = {
        "Content-Type": r.headers["Content-Type"],
    }
    return Response(r.text, headers=response_headers, status_code=200)
