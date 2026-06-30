import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_missing_messages(client):
    response = await client.post("/api/chat", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_status_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
