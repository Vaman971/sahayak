from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from voice_gateway.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    request = await client.get("/healthz")
    assert request.status_code == 200
    assert request.json() == {"status": "ok"}


async def test_readyz_returns_ready(client: AsyncClient) -> None:
    request = await client.get("/readyz")
    assert request.status_code == 200
