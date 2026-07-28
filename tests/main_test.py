"""Tests for the jiradataproxy.main module."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from safir.dependencies.http_client import http_client_dependency

from jiradataproxy import main


@pytest.mark.asyncio
async def test_lifespan_closes_http_client() -> None:
    """The application lifespan closes the shared HTTP client."""
    async with LifespanManager(main.app):
        http_client = await http_client_dependency()
        assert not http_client.is_closed

    assert http_client_dependency.http_client is None
    assert http_client.is_closed
