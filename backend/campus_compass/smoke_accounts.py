"""Exercise real SQL and HTTP account flows inside one rolled-back transaction.

No email is delivered: the account-message transport is replaced with a local
capture. Only randomly generated example.invalid accounts are used.
"""
import json
import secrets
from contextlib import ExitStack
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from fastapi.testclient import TestClient


def run():
    from backend.model_planner.main import app
    from backend.model_planner import auth, completed_courses
    from backend.campus_compass import routes, notifications, mailer
    from scraper.sync_db import get_db_connection

    connection = get_db_connection()

    class Transaction:
        def cursor(self, *args, **kwargs):
            return connection.cursor(*args, **kwargs)

        def commit(self):
            pass

        def close(self):
            pass

    captured = []
    transport = lambda email, subject, text: captured.append(text)
    headers = {"origin": "http://localhost:8080", "x-pathway-request": "1"}
    password = secrets.token_urlsafe(24)
    accounts = [f"integration-{secrets.token_hex(10)}@example.invalid" for _ in range(2)]
    checks = []
    try:
        with ExitStack() as stack:
            for module in (auth, completed_courses, routes, notifications):
                stack.enter_context(patch.object(module, "get_db_connection", lambda: Transaction()))
            stack.enter_context(patch.object(mailer, "configured", lambda: True))
            stack.enter_context(patch.object(mailer, "deliver_account_message", transport))
            first, second, old_session = TestClient(app), TestClient(app), TestClient(app)
            for client, email in zip((first, second), accounts):
                assert client.post("/api/auth/signup", headers=headers, json={"email": email, "password": password}).status_code == 200
                assert client.get("/api/auth/me").json()["logged_in"]
            checks.append("signup and shared session")
            assert old_session.post("/api/auth/login", headers=headers, json={"email": accounts[0], "password": password}).status_code == 200
            profile = {"transfer_stage": "exploring", "major": "Computer Science", "interests": ["robotics"]}
            assert first.put("/api/compass/profile", headers=headers, json=profile).status_code == 200
            assert first.get("/api/compass/profile").json()["profile"] == profile
            assert second.get("/api/compass/profile").json()["profile"]["interests"] == []
            assert first.get("/api/completed-courses").status_code == 200
            checks.append("profile persistence and account isolation")
            preference = first.put("/api/compass/email-preferences", headers=headers, json={"enabled": True}).json()
            assert preference["enabled"] and not preference["pending"]
            assert not captured, "Website opt-in must not send a confirmation email"
            assert first.get("/api/compass/email-preferences").json()["enabled"]
            assert not second.get("/api/compass/email-preferences").json()["enabled"]
            assert first.put("/api/compass/email-preferences", headers=headers, json={"enabled": False}).status_code == 200
            checks.append("immediate email opt-in and unsubscribe preference")
            assert first.post("/api/auth/forgot-password", headers=headers, json={"email": accounts[0]}).status_code == 200
            text = captured.pop()
            token = parse_qs(urlsplit(next(line for line in text.splitlines() if line.startswith("http"))).fragment)["reset"][0]
            new_password = secrets.token_urlsafe(24)
            assert first.post("/api/auth/reset-password", headers=headers, json={"token": token, "password": new_password}).status_code == 200
            assert not old_session.get("/api/auth/me").json()["logged_in"]
            assert old_session.get("/api/compass/profile").status_code == 401
            assert first.post("/api/auth/reset-password", headers=headers, json={"token": token, "password": new_password}).status_code == 400
            assert first.post("/api/auth/login", headers=headers, json={"email": accounts[0], "password": password}).status_code == 401
            assert first.post("/api/auth/login", headers=headers, json={"email": accounts[0], "password": new_password}).status_code == 200
            checks.append("single-use password reset and old-session revocation")
        return checks
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    try:
        print(json.dumps({"checks": run(), "test_data": "rolled back", "emails_sent": 0}))
    except Exception as exc:
        # No traceback: database driver errors may otherwise reveal credentials.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1)
