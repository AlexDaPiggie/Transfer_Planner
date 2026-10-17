from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from backend.campus_compass import db, priority_agent, notifications, mailer
from backend.campus_compass.daily_email import weekly_events, build_email
from backend.campus_compass.ranking import rank_events
from backend.model_planner.auth import current_user
from starlette.requests import Request


def test_event_cache_roundtrip_and_empty_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "events.db")
    assert db.load_events() is None
    db.save_events([{"title": "Workshop", "date": "2026-10-20", "location": "Campus"}], "2026-10-16T12:00:00+00:00")
    assert db.load_events()[0]["title"] == "Workshop"
    db.save_events([], "2026-10-16T13:00:00+00:00")
    assert db.load_events() == []
    assert db.last_scraped_at() == "2026-10-16T13:00:00+00:00"


def test_openrouter_ranking_preserves_event_identity(monkeypatch):
    from models.src import client
    monkeypatch.setenv("CAMPUS_COMPASS_AI_PROVIDER", "openrouter")
    monkeypatch.setattr(client, "complete", lambda *args, **kwargs: ('[{"id": 0, "tier": "high", "reason": "Transfer preparation"}]', "test-model"))
    original = [{"title": "Transfer workshop", "date": "2026-10-20", "url": "https://example.org/event"}]
    ranked = rank_events({"year": "freshman", "major": "Computer Science"}, original)
    assert ranked[0]["tier"] == "high"
    assert ranked[0]["url"] == original[0]["url"]
    assert "tier" not in original[0]


def test_email_rolling_window_includes_next_week_and_excludes_past():
    events = [{"date": value} for value in ("2026-10-15", "2026-10-16", "2026-10-18", "2026-10-19", "2026-10-23", "2026-10-24", None, "invalid")]
    assert [e["date"] for e in weekly_events(events, date(2026, 10, 16))] == ["2026-10-16", "2026-10-18", "2026-10-19", "2026-10-23"]


def test_email_content_escapes_untrusted_event_html():
    text, html = build_email([{"title": "<script>alert(1)</script>", "url": "javascript:alert(1)", "reason": "<img>", "date": "2026-10-17"}], {}, "https://example.org/#unsubscribe=token", date(2026, 10, 17))
    assert "<script>" not in html
    assert "javascript:" not in html
    assert "&lt;script&gt;" in html
    assert "unsubscribe=token" in text


def test_signed_unsubscribe_token_rejects_tampering(monkeypatch):
    monkeypatch.setenv("PATHWAY_SESSION_SECRET", "test-secret")
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(notifications.router)
    token = notifications.unsubscribe_token(10)
    client = TestClient(app)
    response = client.post("/api/compass/unsubscribe", headers={"origin": "http://localhost:8080", "x-pathway-request": "1"}, json={"token": token + "tampered"})
    assert response.status_code == 400


def test_password_reset_version_invalidates_old_session(monkeypatch):
    from backend.model_planner import auth
    monkeypatch.setattr(auth, "_get_user", lambda *args: {"user_id": 1, "session_version": 2})
    scope = {"type": "http", "session": {"uid": 1, "version": 1}}
    assert current_user(Request(scope)) is None
    assert scope["session"] == {}


def test_email_not_configured_without_sender_identity(monkeypatch):
    for key in ("CAMPUS_COMPASS_EMAIL", "CAMPUS_COMPASS_EMAIL_PASSWORD", "BREVO_SENDER_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BREVO_API_KEY", "test-not-a-real-key")
    assert not mailer.configured()


def test_daily_delivery_claim_prevents_second_send(monkeypatch):
    from backend.campus_compass import daily_email, routes, ranking
    claimed = set()
    sent = []

    class Connection:
        def cursor(self, **kwargs):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=()):
            if sql.startswith("SELECT daily_events"):
                self.row = (True,)
            elif sql.startswith("INSERT INTO pathway_email_deliveries"):
                self.row = None if params in claimed else (params[0],)
                claimed.add(params)

        def fetchall(self):
            return [{"user_id": 7, "email": "test@example.invalid", "year": "", "major": "", "interests": []}]

        def fetchone(self):
            return self.row

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(daily_email, "get_db_connection", Connection)
    monkeypatch.setattr(daily_email, "today", lambda: date(2026, 10, 16))
    monkeypatch.setattr(daily_email, "unsubscribe_token", lambda uid: "test-token")
    monkeypatch.setattr(routes, "load_events", lambda: [{"title": "Workshop", "date": "2026-10-16"}])
    monkeypatch.setattr(ranking, "rank_events", lambda profile, events: events)
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send_email", lambda *args: sent.append(args))
    assert daily_email.run_delivery(send=True)["sent"] == 1
    assert daily_email.run_delivery(send=True)["sent"] == 0
    assert len(sent) == 1


def test_server_serves_site_but_not_local_logs():
    from backend.model_planner.main import app
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/js/services.js").status_code == 200
    assert client.get("/vendor/leaflet/leaflet.js").status_code == 200
    assert client.get("/.local-api-error.log").status_code == 404
    assert client.get("/run_local.ps1").status_code == 404


def test_daily_timezone_is_available_on_windows():
    from backend.campus_compass.daily_email import today
    assert isinstance(today(), date)


def test_no_today_events_skips_email_and_ai_even_with_future_events(monkeypatch):
    from backend.campus_compass import daily_email, routes, ranking

    class Connection:
        def cursor(self, **kwargs): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            assert sql.startswith("SELECT u.user_id"), "No delivery claim should be created"
        def fetchall(self): return [{"user_id": 1}]
        def close(self): pass

    def unexpected(*args, **kwargs):
        raise AssertionError("No AI or mail call expected on a day without events")

    monkeypatch.setattr(daily_email, "get_db_connection", Connection)
    monkeypatch.setattr(daily_email, "today", lambda: date(2026, 10, 17))
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send_email", unexpected)
    monkeypatch.setattr(ranking, "rank_events", unexpected)
    monkeypatch.setattr(routes, "load_events", lambda: [{"title": "Tomorrow's workshop", "date": "2026-10-18"}])
    result = daily_email.run_delivery(send=True)
    assert result["skipped"] == 1
    assert result["sent"] == 0


def test_digest_separates_today_and_next_seven_days_without_five_event_cap():
    events = [{"title": f"Today event {i}", "date": "2026-10-17", "tier": "high"} for i in range(6)]
    events.append({"title": "Next Saturday workshop", "date": "2026-10-24", "tier": "medium"})
    text, html = build_email(events, {}, "https://example.org/#unsubscribe=preview", date(2026, 10, 17))
    assert "Today's events" in html
    assert "Coming up in the next 7 days" in html
    assert "Today event 5" in text
    assert text.index("Today event 5") < text.index("Coming up in the next 7 days") < text.index("Next Saturday workshop")
    assert "Oct 18" in html and "Oct 24" in html


def test_rolling_email_window_crosses_month_and_year_boundaries():
    events = [{"date": value} for value in ("2026-12-31", "2027-01-07", "2027-01-08")]
    assert [event["date"] for event in weekly_events(events, date(2026, 12, 31))] == ["2026-12-31", "2027-01-07"]


def test_digest_keeps_all_today_events_and_only_top_five_upcoming():
    from backend.campus_compass.email_template import select_digest_events
    events = [{"title": f"Today {i}", "date": "2026-10-17", "tier": "low"} for i in range(8)]
    events += [{"title": f"Low future {i}", "date": "2026-10-18", "tier": "low"} for i in range(7)]
    events += [{"title": f"High future {i}", "date": "2026-10-24", "tier": "high"} for i in range(5)]
    events.append({"title": "Outside window", "date": "2026-10-25", "tier": "high"})
    todays, upcoming = select_digest_events(events, date(2026, 10, 17))
    assert len(todays) == 8
    assert len(upcoming) == 5
    assert all(event["title"].startswith("High future") for event in upcoming)
    text, html = build_email(events, {}, "https://example.org/unsubscribe", date(2026, 10, 17))
    assert "Today 7" in text
    assert "High future 4" in text
    assert "Low future" not in text
    assert "Outside window" not in html


def test_preparation_stages_reach_ai_without_inferring_legacy_year(monkeypatch):
    from models.src import client
    from backend.campus_compass.profile_schema import normalize_transfer_stage
    import json
    captured = []

    def complete(messages, *args, **kwargs):
        captured.append(json.loads(messages[1]["content"].split("Here is the data:\n", 1)[1]))
        return '[{"id":0,"tier":"high","reason":"Relevant opportunity"}]', "test-model"

    monkeypatch.setenv("CAMPUS_COMPASS_AI_PROVIDER", "openrouter")
    monkeypatch.setattr(client, "complete", complete)
    for stage in ("exploring", "preparing", "applying", ""):
        rank_events({"transfer_stage": stage, "major": "", "interests": []}, [{"title": "Advising"}])
        profile = captured[-1]["student_profile"]
        assert profile["transfer_stage"] == stage
        assert "year" not in profile
        assert profile["stage_guidance"]
    rank_events({"year": "freshman", "major": "", "interests": []}, [{"title": "Advising"}])
    assert captured[-1]["student_profile"]["transfer_stage"] == ""
    assert normalize_transfer_stage("senior") == ""
    assert normalize_transfer_stage("applying") == "applying"


def test_ranking_normalizes_model_tier_case(monkeypatch):
    from backend.campus_compass import ranking
    monkeypatch.setattr(ranking, "prioritize_events", lambda *_: [
        {"id": 0, "tier": "HIGH", "reason": "Relevant transfer workshop."},
        {"id": 1, "tier": " Medium ", "reason": "Useful campus resource."},
        {"id": 2, "tier": "unexpected", "reason": "Invalid tier."},
    ])
    events = [{"title": str(i), "date": "2026-10-17"} for i in range(3)]
    ranked = ranking.rank_events({}, events)
    assert [event["tier"] for event in ranked] == ["high", "medium", "low"]
    assert all("tier" not in event for event in events)
