"""Campus event APIs using Pathway's existing session and account identity."""
import json
import logging
from contextlib import closing
from datetime import datetime, timezone, timedelta
from threading import Lock

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, AliasChoices

from backend.model_planner.auth import _require_origin
from backend.model_planner.completed_courses import _user_id
from scraper.sync_db import get_db_connection
from .profile_schema import MAJOR_OPTIONS, TRANSFER_STAGE_OPTIONS, normalize_transfer_stage

router = APIRouter(prefix="/api/compass", tags=["campus-compass"])
logger = logging.getLogger(__name__)
event_lock = Lock()


class StudentProfile(BaseModel):
    transfer_stage: str = Field(default="", max_length=40, validation_alias=AliasChoices("transfer_stage", "year"))
    major: str = Field(default="", max_length=160)
    interests: list[str] = Field(default_factory=list, max_length=20)


def load_events(refresh=False):
    # Lazy imports keep the transfer planner available without optional AI deps.
    from . import db, config
    from .geocode_events import geocode_location
    from .scrape_events import scrape_all_events
    with event_lock:
        events = db.load_events()
        if events is not None and not refresh:
            return events
        if refresh and db.last_scraped_at():
            stamp = datetime.fromisoformat(db.last_scraped_at())
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - stamp < timedelta(hours=6):
                return events or []
        try:
            fresh = scrape_all_events(months_ahead=config.SCRAPE_MONTHS_AHEAD)
            if not fresh:
                raise RuntimeError("No fresh campus events returned")
            for event in fresh:
                event.update(geocode_location(event.get("location")))
            db.save_events(fresh, scraped_at=datetime.now(timezone.utc).isoformat())
            return fresh
        except Exception:
            if events is not None:
                logger.warning("Event refresh failed; retaining existing campus event cache")
                return events
            raise


async def refresh_loop():
    import asyncio
    # Browsing requests warm an empty cache; thereafter refresh in the background.
    while True:
        await asyncio.sleep(3600)
        try:
            await asyncio.to_thread(load_events, refresh=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Background event refresh failed (%s)", type(exc).__name__)


@router.get("/profile-options")
def profile_options():
    return {"transfer_stages": TRANSFER_STAGE_OPTIONS, "majors": MAJOR_OPTIONS}


@router.get("/events")
def events():
    try:
        return {"events": load_events()}
    except Exception as exc:
        logger.exception("Campus event loading failed")
        raise HTTPException(503, "Campus events are temporarily unavailable. Please try again.") from exc


@router.get("/profile")
def get_profile(request: Request):
    uid = _user_id(request)
    with closing(get_db_connection()) as conn, conn.cursor() as cur:
        cur.execute("SELECT year, major, interests FROM pathway_student_profiles WHERE user_id = %s", (uid,))
        row = cur.fetchone()
    return {"profile": {"transfer_stage": normalize_transfer_stage(row[0]), "major": row[1], "interests": row[2]} if row else StudentProfile().model_dump()}


@router.put("/profile")
def save_profile(payload: StudentProfile, request: Request):
    _require_origin(request)
    uid = _user_id(request)
    if payload.transfer_stage not in {item["value"] for item in TRANSFER_STAGE_OPTIONS} or (payload.major and payload.major not in MAJOR_OPTIONS):
        raise HTTPException(422, "Choose a valid transfer preparation stage and major.")
    if any(len(value) > 120 for value in payload.interests):
        raise HTTPException(422, "Each interest must be 120 characters or fewer.")
    with closing(get_db_connection()) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pathway_student_profiles (user_id, year, major, interests) VALUES (%s, %s, %s, %s::jsonb) "
            "ON CONFLICT (user_id) DO UPDATE SET year = EXCLUDED.year, major = EXCLUDED.major, "
            "interests = EXCLUDED.interests, updated_at = NOW()",
            (uid, payload.transfer_stage, payload.major, json.dumps(payload.interests)),
        )
        conn.commit()
    return {"profile": payload.model_dump()}


@router.post("/rerank")
def rerank(request: Request):
    _require_origin(request)
    profile = get_profile(request)["profile"]
    profile["transfer_stage"] = ""  # Retired UI preference; do not reuse a previously saved stage.
    try:
        from .ranking import rank_events
        return {"events": rank_events(profile, load_events())}
    except Exception as exc:
        logger.exception("Campus ranking failed")
        raise HTTPException(503, "Personalized recommendations are unavailable. You can still browse events.") from exc
