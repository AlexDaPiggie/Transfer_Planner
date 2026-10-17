"""Opt-in, account-scoped event email preferences and verification."""
import hashlib
import os
from contextlib import closing

from fastapi import APIRouter, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field

from backend.model_planner.auth import _require_origin
from backend.model_planner.completed_courses import _user_id
from scraper.sync_db import get_db_connection
from . import mailer

router = APIRouter(prefix="/api/compass", tags=["campus-notifications"])


class EmailPreference(BaseModel):
    enabled: bool


class EmailToken(BaseModel):
    token: str = Field(min_length=32, max_length=2000)


def unsubscribe_token(user_id):
    secret = os.getenv("PATHWAY_SESSION_SECRET")
    if not secret:
        raise RuntimeError("A persistent session secret is required for notification links")
    return URLSafeTimedSerializer(secret, salt="pathway-unsubscribe").dumps({"uid": user_id})


@router.get("/email-preferences")
def email_preferences(request: Request):
    uid = _user_id(request)
    with closing(get_db_connection()) as conn, conn.cursor() as cur:
        cur.execute("SELECT daily_events, confirmation_token_hash IS NOT NULL FROM pathway_email_preferences WHERE user_id = %s", (uid,))
        row = cur.fetchone()
    return {"enabled": bool(row and row[0]), "pending": False, "available": mailer.configured()}


@router.put("/email-preferences")
def set_email_preferences(payload: EmailPreference, request: Request):
    _require_origin(request)
    uid = _user_id(request)
    if payload.enabled and not mailer.configured():
        raise HTTPException(503, "Daily event emails are not available yet.")
    with closing(get_db_connection()) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pathway_email_preferences (user_id, daily_events, confirmation_token_hash, confirmation_expires_at) "
            "VALUES (%s, %s, NULL, NULL) ON CONFLICT (user_id) DO UPDATE SET "
            "daily_events = EXCLUDED.daily_events, confirmation_token_hash = NULL, "
            "confirmation_expires_at = NULL, updated_at = NOW()",
            (uid, payload.enabled),
        )
        conn.commit()
    return {"enabled": payload.enabled, "pending": False}


@router.post("/confirm-email")
def confirm_email(payload: EmailToken, request: Request):
    _require_origin(request)
    with closing(get_db_connection()) as conn, conn.cursor() as cur:
        cur.execute("UPDATE pathway_email_preferences SET daily_events = TRUE, verified_at = NOW(), confirmation_token_hash = NULL, confirmation_expires_at = NULL, updated_at = NOW() WHERE confirmation_token_hash = %s AND confirmation_expires_at > NOW() RETURNING user_id", (hashlib.sha256(payload.token.encode()).hexdigest(),))
        if not cur.fetchone():
            raise HTTPException(400, "This confirmation link has expired or has already been used.")
        conn.commit()
    return {"message": "Daily campus emails are now enabled. You can turn them off in Campus Compass."}


@router.post("/unsubscribe")
def unsubscribe(payload: EmailToken, request: Request):
    _require_origin(request)
    secret = os.getenv("PATHWAY_SESSION_SECRET")
    if not secret:
        raise HTTPException(503, "Please log in to turn off daily event emails.")
    try:
        data = URLSafeTimedSerializer(secret, salt="pathway-unsubscribe").loads(payload.token, max_age=90 * 86400)
        uid = int(data["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(400, "This unsubscribe link has expired. Log in to manage your email preferences.") from exc
    with closing(get_db_connection()) as conn, conn.cursor() as cur:
        cur.execute("UPDATE pathway_email_preferences SET daily_events = FALSE, confirmation_token_hash = NULL, confirmation_expires_at = NULL, updated_at = NOW() WHERE user_id = %s", (uid,))
        conn.commit()
    return {"message": "Daily campus emails have been turned off."}
