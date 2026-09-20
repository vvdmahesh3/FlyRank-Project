"""Tests for the widget CRUD endpoints."""

import uuid

from fastapi.testclient import TestClient


def _auth_header(client: TestClient, email: str = "owner@test.com", tenant: str = "T") -> dict:
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "testpass123",
        "tenant_name": tenant,
    })
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_widget(client: TestClient, headers: dict) -> dict:
    resp = client.post("/api/v1/widgets", json={
        "name": "Contact Form",
        "widget_type": "contact_form",
        "fields_config": [
            {"name": "name", "label": "Name", "type": "text", "required": True},
            {"name": "email", "label": "Email", "type": "email", "required": True},
        ],
        "allowed_origins": ["http://localhost:5173"],
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def test_create_and_list_widget(client: TestClient):
    headers = _auth_header(client)
    widget = _create_widget(client, headers)
    assert widget["name"] == "Contact Form"
    assert widget["public_id"]

    resp = client.get("/api/v1/widgets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_update_widget_bumps_version(client: TestClient):
    headers = _auth_header(client)
    widget = _create_widget(client, headers)
    original_version = widget["version"]

    resp = client.put(f"/api/v1/widgets/{widget['id']}", json={"name": "Updated"},
                      headers=headers)
    assert resp.status_code == 200
    assert resp.json()["version"] == original_version + 1


def test_tenant_isolation(client: TestClient):
    headers_a = _auth_header(client, email="a@t.com", tenant="Tenant A")
    widget_a = _create_widget(client, headers_a)

    headers_b = _auth_header(client, email="b@t.com", tenant="Tenant B")

    # Tenant B cannot see Tenant A's widget
    resp = client.get(f"/api/v1/widgets/{widget_a['id']}", headers=headers_b)
    assert resp.status_code == 404

    # Tenant B's list is empty
    resp = client.get("/api/v1/widgets", headers=headers_b)
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_get_snippet(client: TestClient):
    headers = _auth_header(client)
    widget = _create_widget(client, headers)
    resp = client.get(f"/api/v1/widgets/{widget['id']}/snippet", headers=headers)
    assert resp.status_code == 200
    assert "<script" in resp.json()["snippet"]
