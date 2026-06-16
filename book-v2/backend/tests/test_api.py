import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_book_list():
    response = client.get("/api/books?page=1&per_page=10")
    assert response.status_code == 200
    assert "books" in response.json()
    assert "total" in response.json()


def test_user_registration():
    response = client.post("/api/auth/register", json={
        "username": "testuser123",
        "email": "test123@example.com",
        "password": "testpassword"
    })
    assert response.status_code == 200
    assert response.json()["username"] == "testuser123"
