"""Tests for the public submission endpoint."""

from fastapi.testclient import TestClient


def _setup(client: TestClient) -> tuple[str, dict]:
    client.post("/api/v1/auth/register", json={
        "email": "pub@test.com",
        "password": "testpass123",
        "tenant_name": "Pub Test",
    })
    resp = client.post("/api/v1/auth/login", json={"email": "pub@test.com", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post("/api/v1/widgets", json={
        "name": "Contact",
        "widget_type": "contact_form",
        "fields_config": [
            {"name": "name", "label": "Name", "type": "text", "required": True},
            {"name": "email", "label": "Email", "type": "email", "required": True},
            {"name": "website_url", "label": "Website", "type": "text", "required": False},
        ],
        "allowed_origins": ["http://localhost:5173"],
    }, headers=headers)
    return resp.json()["public_id"], headers


def test_valid_submission(client: TestClient):
    public_id, _ = _setup(client)
    resp = client.post(f"/api/v1/public/submit/{public_id}", json={
        "data": {"name": "John", "email": "john@example.com"},
    }, headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 201
    assert resp.json()["success"] is True


def test_rejected_origin(client: TestClient):
    public_id, _ = _setup(client)
    resp = client.post(f"/api/v1/public/submit/{public_id}", json={
        "data": {"name": "John", "email": "john@example.com"},
    }, headers={"Origin": "http://evil.com"})
    assert resp.status_code == 403


def test_unexpected_field_rejected(client: TestClient):
    public_id, _ = _setup(client)
    resp = client.post(f"/api/v1/public/submit/{public_id}", json={
        "data": {"name": "John", "email": "john@example.com", "bogus": "x"},
    }, headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 422


def test_honeypot_silently_accepted(client: TestClient):
    public_id, _ = _setup(client)
    resp = client.post(f"/api/v1/public/submit/{public_id}", json={
        "data": {"name": "Bot", "email": "bot@bot.com", "website_url": "http://spam.com"},
    }, headers={"Origin": "http://localhost:5173"})
    # Returns success to trick the bot, but submission is discarded
    assert resp.status_code in (200, 201)
    assert resp.json()["success"] is True


def test_cors_preflight(client: TestClient):
    public_id, _ = _setup(client)
    resp = client.options(f"/api/v1/public/submit/{public_id}", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
    })
    assert resp.status_code == 204
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
