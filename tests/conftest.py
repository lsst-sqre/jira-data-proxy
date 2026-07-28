"""Test fixtures for jira-data-proxy tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import HttpUrl, SecretStr

from jiradataproxy import main
from jiradataproxy.config import config

from .support.constants import (
    TEST_BASE_URL,
    TEST_JIRA_BASE_URL,
    TEST_JIRA_PASSWORD,
    TEST_JIRA_USERNAME,
)


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    # httpx 0.26 types the ASGITransport app parameter with dict-based ASGI
    # scopes, while Starlette (and therefore FastAPI) uses MutableMapping, so
    # mypy rejects the assignment. httpx 0.27 relaxed the type; drop the
    # ignore comment when httpx is unpinned.
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(
        transport=transport, base_url=TEST_BASE_URL
    ) as client:
        yield client


@pytest.fixture
def jira_base_url(monkeypatch: pytest.MonkeyPatch) -> str:
    """Point the application at a mock Jira server.

    Also replaces the Jira credentials with known values so that tests can
    assert on the basic auth the application sends upstream regardless of how
    ``JIRA_USERNAME`` and ``JIRA_PASSWORD`` were set in the environment.
    """
    monkeypatch.setattr(config, "jira_base_url", HttpUrl(TEST_JIRA_BASE_URL))
    monkeypatch.setattr(config, "jira_username", TEST_JIRA_USERNAME)
    monkeypatch.setattr(config, "jira_password", SecretStr(TEST_JIRA_PASSWORD))
    return TEST_JIRA_BASE_URL
