import pytest
import httpx


@pytest.mark.anyio
async def test_health_check():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_book_list():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get("/api/books?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert "books" in data
        assert "total" in data


@pytest.mark.anyio
async def test_user_registration():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post("/api/auth/register", json={
            "username": "testuser123",
            "email": "test123@example.com",
            "password": "testpassword"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser123"
