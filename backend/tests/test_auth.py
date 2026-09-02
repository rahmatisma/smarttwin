from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.core import auth
from app.core.config import settings


client = TestClient(app)


def test_protected_endpoint_allows_local_mode(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", False)
    response = client.post("/api/v1/simulation/stop")
    assert response.status_code == 200


def test_protected_endpoint_requires_token_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    response = client.post("/api/v1/simulation/stop")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_protected_endpoint_rejects_non_operator(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    fake_client = SimpleNamespace(
        auth=SimpleNamespace(
            get_user=lambda _token: SimpleNamespace(
                user=SimpleNamespace(
                    id="user-1",
                    email="viewer@example.test",
                    app_metadata={"role": "viewer"},
                )
            )
        )
    )
    monkeypatch.setattr(auth, "get_supabase", lambda: fake_client)

    response = client.post(
        "/api/v1/simulation/stop",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 403


def test_protected_endpoint_allows_operator(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    fake_client = SimpleNamespace(
        auth=SimpleNamespace(
            get_user=lambda _token: SimpleNamespace(
                user=SimpleNamespace(
                    id="user-1",
                    email="operator@example.test",
                    app_metadata={"role": "operator"},
                )
            )
        )
    )
    monkeypatch.setattr(auth, "get_supabase", lambda: fake_client)

    response = client.post(
        "/api/v1/simulation/stop",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 200
