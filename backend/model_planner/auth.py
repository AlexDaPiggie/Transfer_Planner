"""Account-only authentication endpoints for Pathway (no course/profile storage)."""
import os
import re
from contextlib import closing

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from werkzeug.security import check_password_hash, generate_password_hash

from scraper.sync_db import get_db_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class GoogleCredential(BaseModel):
    credential: str = Field(min_length=1, max_length=20000)


def _require_origin(request: Request) -> None:
    """Block CSRF on cookie-authenticated POST endpoints (including sign-in)."""
    origins = os.getenv(
        "PATHWAY_ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
    ).split(",")
    if (request.headers.get("origin") not in [x.strip() for x in origins]
            or request.headers.get("x-pathway-request") != "1"):
        raise HTTPException(status_code=403, detail="Untrusted request origin.")


def _valid_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email.")
    return email


def _get_user(where: str, value):
    # `where` is only ever a hardcoded string below, never browser-provided SQL.
    if where not in ("email", "google_sub", "user_id"):
        raise ValueError("Invalid lookup field")
    with closing(get_db_connection()) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"SELECT user_id, email, password_hash, google_sub FROM pathway_users WHERE {where} = %s",
            (value,),
        )
        return cur.fetchone()


def _public_user(user):
    return {"user_id": user["user_id"], "email": user["email"]}


def _sign_in(request: Request, user):
    request.session.clear()
    request.session["uid"] = user["user_id"]
    return {"logged_in": True, "user": _public_user(user)}


@router.get("/config")
def config():
    # A Google OAuth *client ID* is public; never return a client secret.
    return {"google_client_id": os.getenv("GOOGLE_CLIENT_ID", "")}


@router.post("/signup")
def signup(payload: Credentials, request: Request):
    _require_origin(request)
    email = _valid_email(payload.email)
    if len(payload.password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")
    password_hash = generate_password_hash(payload.password, method="scrypt")
    try:
        with closing(get_db_connection()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO pathway_users (email, password_hash) VALUES (%s, %s) "
                    "RETURNING user_id, email",
                    (email, password_hash),
                )
                user = cur.fetchone()
                conn.commit()
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="This email already has an account.")
    return _sign_in(request, user)


@router.post("/login")
def login(payload: Credentials, request: Request):
    _require_origin(request)
    email = _valid_email(payload.email)
    user = _get_user("email", email)
    if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _sign_in(request, user)


@router.post("/google")
def google_login(payload: GoogleCredential, request: Request):
    _require_origin(request)
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")
    try:
        claims = id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), client_id
        )
    except Exception as exc:
        # Do not return an untrusted token or Google's error details.
        raise HTTPException(status_code=401, detail="Invalid Google sign-in.") from exc
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email or claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google account cannot be verified.")
    email = _valid_email(email)
    user = _get_user("google_sub", sub)
    if user:
        return _sign_in(request, user)
    # Never link an existing email/password account merely by matching email.
    if _get_user("email", email):
        raise HTTPException(
            status_code=409,
            detail="This email is already registered. Please sign in with your password.",
        )
    try:
        with closing(get_db_connection()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO pathway_users (email, google_sub) VALUES (%s, %s) "
                    "RETURNING user_id, email",
                    (email, sub),
                )
                user = cur.fetchone()
                conn.commit()
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="This Google account was already registered. Try signing in again.")
    return _sign_in(request, user)


@router.get("/me")
def me(request: Request):
    uid = request.session.get("uid")
    if not uid:
        return {"logged_in": False}
    user = _get_user("user_id", uid)
    if not user:
        request.session.clear()
        return {"logged_in": False}
    return {"logged_in": True, "user": _public_user(user)}


@router.post("/logout")
def logout(request: Request):
    _require_origin(request)
    request.session.clear()
    return {"logged_in": False}
