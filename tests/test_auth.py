"""Tests for the auth endpoints."""

from fastapi.testclient import TestClient


def test_register_and_login(client: TestClient):
    resp = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "tenant_name": "Test Tenant",
        "full_name": "Test User",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    assert token

    resp = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_register_duplicate_email(client: TestClient):
    payload = {
        "email": "dup@example.com",
        "password": "testpass123",
        "tenant_name": "T1",
    }
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_login_wrong_password(client: TestClient):
    client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com",
        "password": "correctpass",
        "tenant_name": "T",
    })
    resp = client.post("/api/v1/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401
