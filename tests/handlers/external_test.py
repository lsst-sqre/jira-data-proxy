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
async def test_proxy_follows_redirects(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """Redirects from Jira are followed and the final response returned.

    Some Jira endpoints redirect, so the shared HTTP client that safir
    provides is built with ``follow_redirects=True``. This pins that
    behavior: the proxy must return the redirect target's response rather
    than handing the 302 back to the caller. The credentials are expected to
    survive a same-origin hop, since that is how an authenticated Jira
    redirect is meant to work.
    """
    redirect = respx_mock.get(
        f"{jira_base_url}rest/api/2/issue/DM-42460"
    ).respond(
        302,
        headers={"Location": f"{jira_base_url}rest/api/2/issue/DM-42461"},
    )
    target = respx_mock.get(
        f"{jira_base_url}rest/api/2/issue/DM-42461"
    ).respond(json={"key": "DM-42461"})

    response = await client.get(proxy_url("rest/api/2/issue/DM-42460"))

    assert response.status_code == 200
    assert response.json() == {"key": "DM-42461"}
    assert redirect.call_count == 1
    assert target.call_count == 1
    assert "Authorization" in target.calls.last.request.headers


@pytest.mark.asyncio
async def test_proxy_drops_credentials_on_cross_origin_redirect(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """Jira credentials do not follow a redirect to a different host.

    Following redirects (see ``test_proxy_follows_redirects``) is safe only
    because httpx strips the ``Authorization`` header when a redirect crosses
    origins. This pins that guarantee: were it to regress, a redirect away
    from Jira would hand the bot account's credentials to another host.
    """
    redirect = respx_mock.get(f"{jira_base_url}secure/Dashboard.jspa").respond(
        302, headers={"Location": "https://elsewhere.example.org/landing"}
    )
    elsewhere = respx_mock.get(
        "https://elsewhere.example.org/landing"
    ).respond(json={"ok": True})

    response = await client.get(proxy_url("secure/Dashboard.jspa"))

    assert response.status_code == 200
    assert redirect.call_count == 1
    assert elsewhere.call_count == 1
    assert "Authorization" in redirect.calls.last.request.headers
    assert "Authorization" not in elsewhere.calls.last.request.headers


@pytest.mark.asyncio
async def test_proxy_refuses_absolute_url_path(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """An absolute URL in the proxied path does not redirect the request.

    ``urljoin`` returns its second argument unchanged when that argument is
    an absolute URL, so without a check of its own the proxy would send the
    Jira bot account's credentials to whatever host the caller named.
    """
    evil = respx_mock.get("https://evil.example.org/steal").respond(json={})

    response = await client.get(proxy_url("https://evil.example.org/steal"))

    assert response.status_code == 404
    assert evil.call_count == 0


@pytest.mark.asyncio
async def test_proxy_refuses_protocol_relative_path(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """A protocol-relative path does not redirect the request.

    ``urljoin`` also passes ``//host/path`` through unchanged, inheriting the
    base URL's scheme.
    """
    evil = respx_mock.get("https://evil.example.org/steal").respond(json={})

    response = await client.get(proxy_url("//evil.example.org/steal"))

    assert response.status_code == 404
    assert evil.call_count == 0


@pytest.mark.asyncio
async def test_proxy_refuses_percent_encoded_absolute_url_path(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """Percent-encoding the separator does not slip an absolute URL through.

    An ingress that merges duplicate slashes neutralizes the literal forms of
    this attack, but ``https:%2F%2Fevil.example.org/`` reaches the
    application with its slashes intact and is decoded to an absolute URL
    only once Starlette has parsed the path. The application cannot delegate
    this check to its ingress.
    """
    evil = respx_mock.get("https://evil.example.org/steal").respond(json={})

    response = await client.get(
        proxy_url("https:%2F%2Fevil.example.org/steal")
    )

    assert response.status_code == 404
    assert evil.call_count == 0


@pytest.mark.asyncio
async def test_proxy_refuses_authority_with_userinfo(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """The Jira host appearing as userinfo does not make a URL acceptable.

    ``https://jira.example.org@evil.example.org/`` names ``evil.example.org``
    as its host, and the check has to agree with the HTTP client about that
    rather than pattern-matching on the URL text.
    """
    evil = respx_mock.get("https://evil.example.org/").respond(json={})

    response = await client.get(
        proxy_url("https://jira.example.org@evil.example.org/")
    )

    assert response.status_code == 404
    assert evil.call_count == 0


@pytest.mark.asyncio
async def test_proxy_refuses_scheme_change(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """The same host over a different scheme is refused.

    Downgrading to ``http`` would put the basic auth credentials on the wire
    in the clear.
    """
    insecure = respx_mock.get(
        "http://jira.example.org/rest/api/2/myself"
    ).respond(json={})

    response = await client.get(
        proxy_url("http://jira.example.org/rest/api/2/myself")
    )

    assert response.status_code == 404
    assert insecure.call_count == 0


@pytest.mark.asyncio
async def test_proxy_refuses_unparseable_path(
    client: AsyncClient, respx_mock: respx.Router, jira_base_url: str
) -> None:
    """A path that cannot be parsed as a URL is refused rather than raised.

    ``https://[/`` makes ``urljoin`` itself raise, which would otherwise
    surface as a 500.
    """
    response = await client.get(proxy_url("https://[/"))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_proxy_refuses_path_escaping_base_url_path(
    client: AsyncClient,
    respx_mock: respx.Router,
    jira_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative segments cannot climb above a base URL with a path.

    Starlette percent-decodes the path before the handler sees it, so
    ``%2E%2E`` arrives as ``..`` and ``urljoin`` resolves it. The result stays
    on the Jira host, so this leaks no credentials, but it escapes the
    configured base URL and is refused for that reason.
    """
    monkeypatch.setattr(
        config, "jira_base_url", HttpUrl("https://jira.example.org/jira/")
    )
    outside = respx_mock.get(
        "https://jira.example.org/secure/Dashboard.jspa"
    ).respond(json={})

    response = await client.get(proxy_url("%2E%2E/secure/Dashboard.jspa"))

    assert response.status_code == 404
    assert outside.call_count == 0


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
