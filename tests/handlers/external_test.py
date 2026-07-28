"""Tests for the jiradataproxy.handlers.external module and routes."""

from __future__ import annotations

from base64 import b64encode

import pytest
import respx
from httpx import AsyncClient, Response
from pydantic import HttpUrl

from jiradataproxy.config import config

from ..support.constants import TEST_JIRA_PASSWORD, TEST_JIRA_USERNAME


def proxy_url(path: str) -> str:
    """Build a URL for the proxy's external route."""
    return f"{config.path_prefix}/{path}"


@pytest.mark.asyncio
async def test_proxy_get(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """The proxy forwards a GET to the corresponding Jira URL."""
    route = respx_mock.get(
        f"{jira_base_url}rest/api/2/issue/DM-42460"
    ).respond(json={"key": "DM-42460"})

    response = await client.get(proxy_url("rest/api/2/issue/DM-42460"))

    assert response.status_code == 200
    assert response.json() == {"key": "DM-42460"}
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_proxy_sends_basic_auth_and_accept_header(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """The proxy authenticates to Jira and asks for JSON."""
    route = respx_mock.get(f"{jira_base_url}rest/api/2/myself").respond(
        json={"name": TEST_JIRA_USERNAME}
    )

    response = await client.get(proxy_url("rest/api/2/myself"))

    assert response.status_code == 200
    request = route.calls.last.request
    credentials = f"{TEST_JIRA_USERNAME}:{TEST_JIRA_PASSWORD}".encode()
    expected = b64encode(credentials).decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    assert request.headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_proxy_normalizes_base_url_without_trailing_slash(
    client: AsyncClient,
    respx_mock: respx.Router,
    jira_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A base URL without a trailing slash still joins cleanly.

    The configuration model validates that ``jira_base_url`` ends with a
    trailing slash, but the handler normalizes the URL itself as well so that
    a base URL with a path component cannot swallow its last segment.
    """
    monkeypatch.setattr(
        config, "jira_base_url", HttpUrl("https://jira.example.org/jira")
    )
    route = respx_mock.get(
        "https://jira.example.org/jira/rest/api/2/issue/DM-42460"
    ).respond(json={"key": "DM-42460"})

    response = await client.get(proxy_url("rest/api/2/issue/DM-42460"))

    assert response.status_code == 200
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_proxy_passes_query_string(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """Query parameters are re-encoded and passed through to Jira."""
    route = respx_mock.get(f"{jira_base_url}rest/api/2/search").respond(
        json={"issues": []}
    )

    response = await client.get(
        proxy_url("rest/api/2/search"),
        params={"jql": "project = DM ORDER BY created", "maxResults": "5"},
    )

    assert response.status_code == 200
    request = route.calls.last.request
    assert request.url.params["jql"] == "project = DM ORDER BY created"
    assert request.url.params["maxResults"] == "5"


@pytest.mark.asyncio
async def test_proxy_collapses_repeated_query_parameters(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """Repeated query parameters are collapsed to the last value.

    This documents current behavior rather than endorsing it: the handler
    builds a ``dict`` from the query parameters, so only the last value of a
    repeated parameter (such as Jira's ``fields``) reaches Jira.
    """
    route = respx_mock.get(f"{jira_base_url}rest/api/2/search").respond(
        json={"issues": []}
    )

    response = await client.get(
        proxy_url("rest/api/2/search") + "?fields=key&fields=summary"
    )

    assert response.status_code == 200
    request = route.calls.last.request
    assert request.url.params.get_list("fields") == ["summary"]


@pytest.mark.asyncio
async def test_proxy_filters_response_headers(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """Only the content type is forwarded from Jira's response."""
    route = respx_mock.get(f"{jira_base_url}rest/api/2/issue/DM-42460").mock(
        return_value=Response(
            200,
            json={"key": "DM-42460"},
            headers={
                "Set-Cookie": "JSESSIONID=secret; Path=/",
                "X-AUSERNAME": "jira-bot",
                "X-Seraph-LoginReason": "OK",
            },
        )
    )

    response = await client.get(proxy_url("rest/api/2/issue/DM-42460"))

    assert response.status_code == 200
    assert route.call_count == 1
    assert response.headers["content-type"] == "application/json"
    assert "set-cookie" not in response.headers
    assert "x-ausername" not in response.headers
    assert "x-seraph-loginreason" not in response.headers


@pytest.mark.asyncio
async def test_proxy_passes_error_status_and_body(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """A non-200 response from Jira is passed through unchanged."""
    body = {"errorMessages": ["Issue does not exist."], "errors": {}}
    route = respx_mock.get(f"{jira_base_url}rest/api/2/issue/DM-0").respond(
        404, json=body
    )

    response = await client.get(proxy_url("rest/api/2/issue/DM-0"))

    assert response.status_code == 404
    assert response.json() == body
    assert response.headers["content-type"] == "application/json"
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_proxy_passes_non_json_body(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """Jira responses that are not JSON are passed through as text."""
    route = respx_mock.get(f"{jira_base_url}secure/Dashboard.jspa").respond(
        200, html="<html><body>Dashboard</body></html>"
    )

    response = await client.get(proxy_url("secure/Dashboard.jspa"))

    assert response.status_code == 200
    assert response.text == "<html><body>Dashboard</body></html>"
    assert response.headers["content-type"].startswith("text/html")
    assert route.call_count == 1
