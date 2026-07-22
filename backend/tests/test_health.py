import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "LivePokerOPS"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_endpoint_method_not_allowed(client: AsyncClient):
    response = await client.post("/health")
    assert response.status_code == 405
