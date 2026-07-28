"""Test fixtures for jira-data-proxy tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from jiradataproxy import main


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
        transport=transport, base_url="https://example.com/"
    ) as client:
        yield client
