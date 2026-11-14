"""Verify retired endpoints and the shared account/site features they used."""
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.model_planner import auth
from backend.model_planner.main import app


@pytest.mark.parametrize("path", [
    "/api/compass/events",
    "/api/compass/profile",
    "/api/compass/profile-options",
    "/api/compass/email-preferences",
])
def test_retired_api_is_unavailable(path):
    # Enter lifespan too: the app must start without event jobs or dependencies.
    with TestClient(app) as client:
        assert client.get(path).status_code == 404
        assert not any(p.startswith("/api/compass") for p in client.get("/openapi.json").json()["paths"])


def test_server_serves_remaining_services_without_exposing_local_files():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/").status_code == 200
        assert client.get("/js/services.js").status_code == 200
        assert client.get("/chatbot/").status_code == 200
        for path in ("/vendor/leaflet/leaflet.js", "/.local-api-error.log", "/run_local.ps1"):
            assert client.get(path).status_code == 404


def test_session_version_invalidates_old_session(monkeypatch):
    monkeypatch.setattr(auth, "_get_user", lambda *args: {"user_id": 1, "session_version": 2})
    scope = {"type": "http", "session": {"uid": 1, "version": 1}}
    assert auth.current_user(Request(scope)) is None
    assert scope["session"] == {}


def test_auth_config_only_exposes_google_client_id():
    with TestClient(app) as client:
        assert set(client.get("/api/auth/config").json()) == {"google_client_id"}


@pytest.mark.parametrize("path", ["/api/auth/forgot-password", "/api/auth/reset-password"])
def test_email_recovery_endpoints_are_unavailable(path):
    with TestClient(app) as client:
        assert client.post(path, json={"email": "test@example.invalid"}).status_code == 404
        assert path not in client.get("/openapi.json").json()["paths"]
