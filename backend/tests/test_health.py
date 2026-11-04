import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "lumora" in data["service"].lower()


@pytest.mark.asyncio
async def test_health_can_run_a_database_query(async_client):
    res = await async_client.get("/api/v1/health?check_db=true")
    assert res.status_code == 200
    assert res.json()["database"]["status"] in ("connected", "in_memory_fallback")
