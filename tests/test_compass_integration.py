"""Verify session isolation and CSRF at the integrated Campus Compass boundary."""
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.campus_compass import routes
from backend.model_planner import auth


@pytest.fixture
def client(monkeypatch):
    profiles = {}

    class Connection:
        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params):
            if sql.startswith("INSERT"):
                profiles[params[0]] = (params[1], params[2], json.loads(params[3]))
            else:
                self.row = profiles.get(params[0])

        def fetchone(self):
            return self.row

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(routes, "get_db_connection", Connection)
    monkeypatch.setattr(auth, "_get_user", lambda where, uid: {"user_id": uid, "session_version": 0})
    app = FastAPI()

    @app.middleware("http")
    async def session(request: Request, call_next):
        # Only the test harness injects identities. Production uses signed cookies.
        uid = request.headers.get("test-user")
        request.scope["session"] = {"uid": int(uid)} if uid else {}
        return await call_next(request)

    app.include_router(routes.router)
    return TestClient(app)


def headers(uid="1"):
    return {"test-user": uid, "origin": "http://localhost:8080", "x-pathway-request": "1"}


def test_profile_requires_login(client):
    assert client.get("/api/compass/profile").status_code == 401
    assert client.put("/api/compass/profile", headers={"origin": "http://localhost:8080", "x-pathway-request": "1"}, json={}).status_code == 401


def test_profile_is_scoped_to_signed_in_user(client):
    data = {"transfer_stage": "exploring", "major": "", "interests": ["robotics"]}
    assert client.put("/api/compass/profile", headers=headers(), json=data).status_code == 200
    assert client.get("/api/compass/profile", headers=headers()).json()["profile"] == data
    assert client.get("/api/compass/profile", headers=headers("2")).json()["profile"]["interests"] == []


def test_writes_reject_foreign_origin_and_invalid_vocabulary(client):
    untrusted = {**headers(), "origin": "https://untrusted.example"}
    assert client.put("/api/compass/profile", headers=untrusted, json={}).status_code == 403
    assert client.put("/api/compass/profile", headers=headers(), json={"transfer_stage": "invalid"}).status_code == 422
    assert client.post("/api/compass/rerank", headers=untrusted).status_code == 403


def test_browse_events_without_login_and_fail_gracefully(client, monkeypatch):
    monkeypatch.setattr(routes, "load_events", lambda: [{"title": "Transfer workshop"}])
    assert client.get("/api/compass/events").json()["events"][0]["title"] == "Transfer workshop"

    def fail():
        raise RuntimeError("private upstream details")

    monkeypatch.setattr(routes, "load_events", fail)
    response = client.get("/api/compass/events")
    assert response.status_code == 503
    assert "private upstream details" not in response.text


def test_ranking_requires_account_before_loading_ai(client):
    assert client.post("/api/compass/rerank", headers={"origin": "http://localhost:8080", "x-pathway-request": "1"}).status_code == 401


def test_major_can_be_cleared_and_interest_only_profile_reaches_ranking(client, monkeypatch):
    from backend.campus_compass import ranking
    captured = []
    monkeypatch.setattr(routes, "load_events", lambda: [{"title": "Photography workshop"}])

    def rank(profile, events):
        captured.append(profile)
        return events

    monkeypatch.setattr(ranking, "rank_events", rank)
    first = {"transfer_stage": "", "major": "Computer Science", "interests": ["robotics"]}
    assert client.put("/api/compass/profile", headers=headers(), json=first).status_code == 200
    cleared = {"transfer_stage": "", "major": "", "interests": ["photography"]}
    assert client.put("/api/compass/profile", headers=headers(), json=cleared).status_code == 200
    assert client.get("/api/compass/profile", headers=headers()).json()["profile"] == cleared
    assert client.post("/api/compass/rerank", headers=headers()).status_code == 200
    assert captured == [cleared]
    assert client.put("/api/compass/profile", headers=headers(), json={}).status_code == 200
    assert client.get("/api/compass/profile", headers=headers()).json()["profile"] == {"transfer_stage": "", "major": "", "interests": []}
