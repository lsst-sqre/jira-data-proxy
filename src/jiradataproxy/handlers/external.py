"""Handlers for the app's external API, ``/jira-data-proxy/``."""

from urllib.parse import urlencode, urljoin

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from httpx import URL, AsyncClient, InvalidURL
from safir.dependencies.http_client import http_client_dependency
from safir.dependencies.logger import logger_dependency
from structlog.stdlib import BoundLogger

from ..config import config

__all__ = ["external_router", "get_jira", "resolve_jira_url"]

external_router = APIRouter()
"""FastAPI router for all external handlers."""


def resolve_jira_url(path: str) -> URL | None:
    """Resolve a proxied request path to an upstream Jira URL.

    Parameters
    ----------
    path
        Path from the request, relative to the proxy's route prefix. This is
        entirely under the caller's control.

    Returns
    -------
    httpx.URL or None
        The upstream URL to request, or `None` if `path` does not resolve to
        a URL at or below the configured Jira base URL.

    Notes
    -----
    The result of joining `path` onto the base URL cannot be trusted.
    `urllib.parse.urljoin` returns its second argument unchanged when that
    argument is an absolute (``https://evil.example.org/``) or
    protocol-relative (``//evil.example.org/``) URL, so on its own it offers
    no containment at all. Because the proxy attaches the Jira bot account's
    basic auth credentials to the upstream request, an unchecked join would
    hand those credentials to any host the caller cares to name.

    The joined URL is therefore parsed and checked against the base URL, and
    the parsed `httpx.URL` is what the caller sends upstream. Validating with
    the same parser that ultimately issues the request leaves no room for the
    two to disagree about which host a URL names.
    """
    # The configuration model validates that jira_base_url ends with a
    # trailing slash, but normalize here as well: without the trailing slash,
    # urljoin replaces the last segment of a base URL that has a path rather
    # than extending it.
    base_url_str = str(config.jira_base_url)
    if not base_url_str.endswith("/"):
        base_url_str += "/"
    base_url = URL(base_url_str)

    # Both urljoin and httpx reject some syntactically invalid URLs, and a
    # caller can provoke either. Treat an unparseable result the same as one
    # that points somewhere else.
    try:
        url = URL(urljoin(base_url_str, path, allow_fragments=False))
    except InvalidURL, ValueError:
        return None

    origin = (url.scheme, url.host, url.port)
    if origin != (base_url.scheme, base_url.host, base_url.port):
        return None

    # Keep the request within the base URL's path as well, so that a base URL
    # with a path component cannot be escaped upwards with ``..`` segments.
    if not url.path.startswith(base_url.path):
        return None

    return url


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
    url = resolve_jira_url(path)
    if url is None:
        logger.warning(
            "Refused a request that resolves outside of Jira",
            path=path,
        )
        raise HTTPException(
            status_code=404,
            detail="Path does not resolve to a URL on the Jira server",
        )

    if request.query_params:
        qs = urlencode(dict(request.query_params.items()))
        url = url.copy_with(query=qs.encode())

    logger.debug(
        "Got Jira request",
        path=path,
        jira_url=str(url),
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
