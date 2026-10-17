"""Compare actual AI responses using fictional events and example profiles.

No account or saved student profile is read or modified. The events are explicit
test fixtures, not claimed to be real campus announcements.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


def check():
    load_dotenv(".env")
    load_dotenv(".env.local", override=True)
    from .ranking import rank_events
    date = (datetime.now(ZoneInfo("America/Los_Angeles"))).date() + timedelta(days=4)
    fixtures = [
        {"title": "Robotics programming lab", "description": "Hands-on Python programming, robot sensors and software engineering projects for computer science students."},
        {"title": "Biology research lab workshop", "description": "Explore cell biology, genetics, microscopy and biology undergraduate research opportunities."},
        {"title": "Photography club photo walk", "description": "Practice photography, camera composition and photo editing with other photography enthusiasts."},
        {"title": "University application deadline", "description": "Required transfer application deadline. All students applying to university must submit their applications."},
    ]
    fixtures = [{**event, "date": date.isoformat(), "location": "Example test venue"} for event in fixtures]
    profiles = {
        "general": {"year": "", "major": "", "interests": []},
        "computer_science": {"year": "", "major": "Computer Science", "interests": []},
        "biology": {"year": "", "major": "Biology", "interests": []},
        "photography_interest_only": {"year": "", "major": "", "interests": ["photography"]},
    }
    results = {}
    for name, profile in profiles.items():
        ranked = rank_events(profile, fixtures)
        results[name] = {event["title"]: {"tier": event["tier"], "reason": event["reason"]} for event in ranked}
        print(json.dumps({"profile": name, "ranking": results[name]}), flush=True)
    titles = [event["title"] for event in fixtures]
    major_changes = [title for title in titles if results["computer_science"][title]["tier"] != results["biology"][title]["tier"]]
    interest_changes = [title for title in titles if results["general"][title]["tier"] != results["photography_interest_only"][title]["tier"]]
    summary = {"major_changed_tiers": major_changes, "interest_changed_tiers": interest_changes, "profiles_read_from_database": 0}
    print(json.dumps(summary), flush=True)
    return bool(major_changes and interest_changes)


if __name__ == "__main__":
    try:
        raise SystemExit(0 if check() else 1)
    except Exception as exc:
        print(json.dumps({"personalization_check": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1)
