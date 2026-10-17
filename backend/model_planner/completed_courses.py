"""Store completed *community-college* courses for the signed-in Pathway user."""
import re
from contextlib import closing

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor

from scraper.sync_db import get_db_connection
from backend.model_planner.auth import _require_origin

router = APIRouter(prefix="/api/completed-courses", tags=["completed-courses"])


class CourseSelection(BaseModel):
    source_id: int = Field(gt=0)
    course_code: str = Field(min_length=1, max_length=120)


def _user_id(request: Request) -> int:
    uid = request.session.get("uid")
    if not isinstance(uid, int) or uid <= 0:
        raise HTTPException(status_code=401, detail="Log in to manage completed courses.")
    return uid


def _normalize_code(raw: str) -> str:
    code = re.sub(r"\s+", " ", raw.strip()).upper()
    if not code or len(code) > 120 or any(ord(char) < 32 for char in code):
        raise HTTPException(status_code=422, detail="Invalid course code.")
    return code


@router.get("")
def list_completed_courses(request: Request):
    uid = _user_id(request)
    with closing(get_db_connection()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT source_id, course_code FROM user_completed_courses "
                "WHERE user_id = %s ORDER BY source_id, course_code",
                (uid,),
            )
            return {"courses": [dict(row) for row in cur.fetchall()]}


@router.post("")
def add_completed_course(payload: CourseSelection, request: Request):
    _require_origin(request)
    uid = _user_id(request)
    code = _normalize_code(payload.course_code)
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_completed_courses (user_id, source_id, course_code) "
                "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (uid, payload.source_id, code),
            )
            conn.commit()
    return {"source_id": payload.source_id, "course_code": code, "completed": True}


@router.delete("")
def remove_completed_course(payload: CourseSelection, request: Request):
    _require_origin(request)
    uid = _user_id(request)
    code = _normalize_code(payload.course_code)
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_completed_courses "
                "WHERE user_id = %s AND source_id = %s AND course_code = %s",
                (uid, payload.source_id, code),
            )
            conn.commit()
    return {"source_id": payload.source_id, "course_code": code, "completed": False}
