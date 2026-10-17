"""FastAPI boundary between the browser, verified agreement data, and AI models."""
import json
import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.frontend_files import FrontendFiles
from pydantic import BaseModel, Field

from backend.model_planner.course_board import build_course_board
from backend.model_planner.matrix_engine import compute_overlap_matrix, extract_courses_from_payload
from backend.model_planner.transfer_plan import build_assist_url, build_transfer_plan
from models.src.explainer import answer_student_question, generate_student_summary
from models.src.planner import generate_technical_plan
from models.src.schemas import ChatInput, StudentSummaryInput, TechnicalPlanInput
from scraper.sync_db import get_db_connection

from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import os
import secrets
from backend.model_planner.auth import router as auth_router
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)


@asynccontextmanager
async def lifespan(app):
    from backend.campus_compass.routes import refresh_loop
    refresh_task = asyncio.create_task(refresh_loop())
    task = None
    if os.getenv("PATHWAY_DAILY_EMAILS_ENABLED", "false").lower() in ("true", "1", "yes"):
        from backend.campus_compass.daily_email import delivery_loop
        task = asyncio.create_task(delivery_loop())
    try:
        yield
    finally:
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="De Anza Guide", version="2.1.0", lifespan=lifespan)
auth_secret = os.getenv("PATHWAY_SESSION_SECRET")
if not auth_secret:
    if os.getenv("PATHWAY_ENV") == "production":
        raise RuntimeError("PATHWAY_SESSION_SECRET is required in production")
    print("[auth] WARNING: ephemeral development session key; logins reset after server restart")
    auth_secret = secrets.token_urlsafe(48)
app.add_middleware(SessionMiddleware, secret_key=auth_secret, session_cookie="pathway_session", same_site="lax", https_only=os.getenv("PATHWAY_ENV") == "production")
app.include_router(auth_router)
from backend.model_planner.completed_courses import router as completed_courses_router
app.include_router(completed_courses_router)
from backend.campus_compass.routes import router as compass_router
app.include_router(compass_router)
from backend.campus_compass.notifications import router as notification_router
app.include_router(notification_router)
from backend.deanza_chatbot.routes import router as deanza_chat_router
app.include_router(deanza_chat_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_headers=["*"], allow_methods=["*"], allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"], allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+")
DEFAULT_YEAR_ID = 77
SOURCE_NAMES = {
    51: "Foothill College",
    80: "West Valley College",
    113: "De Anza College",
}

class TargetSelection(BaseModel):
    target_id: int
    target_name: str
    major: str

class PlanRequest(BaseModel):
    year_id: int = DEFAULT_YEAR_ID
    source_ids: list[int] = Field(min_length=1)
    main_source_id: int | None = None
    targets: list[TargetSelection] = Field(min_length=1)

class ChatRequest(BaseModel):
    plan_context: str = Field(min_length=1)
    history: list[dict[str, str]] = Field(default_factory=list)
    message: str = Field(min_length=1)

def label_school(school_id: int, kind: str) -> str:
    return SOURCE_NAMES.get(school_id, f"{kind} #{school_id}")

def decode_payload(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else json.loads(value)


def unpack_agreement_row(row: tuple[Any, ...], requested_year_id: int) -> tuple[int, Any, str]:
    """Accept both current database rows and legacy two-column fixtures."""
    if len(row) == 2:
        return requested_year_id, row[0], row[1]
    return row[0], row[1], row[2]

def catalog_year_ids(year_id: int) -> list[int]:
    """Include prior-year catalog entries so unavailable current-year programs remain selectable."""
    return [year_id, 76] if year_id == 77 else [year_id]


@app.get("/api/health")
def api_health():
    """Confirm that FastAPI is running without requiring a database request."""
    return {"status": "ok"}


@app.get("/api/catalog/sources")
def list_sources(year_id: int = DEFAULT_YEAR_ID):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT source_school_id, institution_name FROM (
                SELECT DISTINCT a.source_school_id AS source_school_id,
                    i.institution_name AS institution_name
                FROM agreements a
                LEFT JOIN institutions i ON i.institution_id=a.source_school_id
                WHERE a.year_id = ANY(%s)
            ) AS sources
            ORDER BY institution_name NULLS LAST, source_school_id""", (catalog_year_ids(year_id),))
        return [{"id": row[0], "name": row[1] or label_school(row[0], "Community college")} for row in cur.fetchall()]
    finally:
        conn.close()

@app.get("/api/catalog/targets")
def list_targets(source_ids: str, year_id: int = DEFAULT_YEAR_ID):
    ids = [int(item) for item in source_ids.split(",") if item.strip().isdigit()]
    if not ids:
        return []
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT target_school_id, institution_name FROM (
                SELECT DISTINCT a.target_school_id AS target_school_id,
                    i.institution_name AS institution_name
                FROM agreements a
                LEFT JOIN institutions i ON i.institution_id=a.target_school_id
                WHERE a.year_id = ANY(%s) AND a.source_school_id = ANY(%s)
            ) AS targets
            ORDER BY institution_name NULLS LAST, target_school_id""", (catalog_year_ids(year_id), ids))
        return [{"id": row[0], "name": row[1] or label_school(row[0], "Transfer school")} for row in cur.fetchall()]
    finally:
        conn.close()

@app.get("/api/catalog/majors")
def list_majors(source_ids: str, target_id: int, year_id: int = DEFAULT_YEAR_ID):
    ids = [int(item) for item in source_ids.split(",") if item.strip().isdigit()]
    if not ids:
        return []
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT major_name FROM agreements WHERE year_id = ANY(%s) AND source_school_id = ANY(%s) AND target_school_id=%s ORDER BY major_name", (catalog_year_ids(year_id), ids, target_id))
        return [{"name": row[0]} for row in cur.fetchall()]
    finally:
        conn.close()

def to_model_input(matrix_result: dict[str, Any], deterministic_plan: dict[str, Any]) -> TechnicalPlanInput:
    rows = [{"course_code": row["course_code"], "course_name": row["course_name"], "targets": row["supported_goals"], "overlap_count": row["supports_count"], "official_url": row["assist_urls"][0]} for row in deterministic_plan["recommended_courses"]]
    if not rows:
        raise HTTPException(status_code=422, detail="The selected agreement has no course rows to plan from.")
    return TechnicalPlanInput(matrix=rows, series_rules=[str(item) for item in matrix_result["series_rules"]], raw_notes=[str(item) for item in matrix_result["raw_notes"]])

def to_frontend_matrix(matrix_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"course_code": row["code"], "course_name": row["title"] or row["code"], "targets": list(row["schools"].keys()), "overlap_count": row["overlap_count"], "official_url": "https://assist.org"} for row in matrix_result["matrix"]]

@app.post("/api/generate-plan")
def api_generate_plan(req: PlanRequest):
    if req.main_source_id is not None and req.main_source_id not in req.source_ids:
        raise HTTPException(status_code=422, detail="Your main community college must be one of the selected colleges.")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        agreements = []
        goal_statuses = [
            {
                "target_id": target.target_id,
                "university": target.target_name,
                "major": target.major,
                "assist_url": None,
                "college_statuses": [],
            }
            for target in req.targets
        ]
        for source_id in req.source_ids:
            for target in req.targets:
                cur.execute("SELECT year_id, raw_json, document_key FROM agreements WHERE year_id=%s AND source_school_id=%s AND target_school_id=%s AND major_name=%s", (req.year_id, source_id, target.target_id, target.major))
                row = cur.fetchone()
                data_year = req.year_id
                if row:
                    data_year, raw_payload, document_key = unpack_agreement_row(row, req.year_id)
                    payload = decode_payload(raw_payload)
                    current_courses, _, _ = extract_courses_from_payload(payload)
                    if not any(course.get("cc_code") for course in current_courses) and req.year_id == 77:
                        cur.execute("SELECT year_id, raw_json, document_key FROM agreements WHERE year_id=76 AND source_school_id=%s AND target_school_id=%s AND major_name=%s", (source_id, target.target_id, target.major))
                        prior_row = cur.fetchone()
                        if prior_row:
                            prior_year, prior_raw_payload, _ = unpack_agreement_row(prior_row, 76)
                            prior_payload = decode_payload(prior_raw_payload)
                            prior_courses, _, _ = extract_courses_from_payload(prior_payload)
                            if any(course.get("cc_code") for course in prior_courses):
                                row = prior_row
                                payload = prior_payload
                                data_year = prior_year
                elif req.year_id == 77:
                    cur.execute("SELECT year_id, raw_json, document_key FROM agreements WHERE year_id=76 AND source_school_id=%s AND target_school_id=%s AND major_name=%s", (source_id, target.target_id, target.major))
                    row = cur.fetchone()
                    if row:
                        data_year, _, _ = unpack_agreement_row(row, 76)
                goal_status = next(item for item in goal_statuses if item["target_id"] == target.target_id and item["major"] == target.major)
                source_name = label_school(source_id, "Community college")
                if row:
                    data_year, raw_payload, document_key = unpack_agreement_row(row, data_year)
                    payload = decode_payload(raw_payload)
                    courses, series_rules, notes = extract_courses_from_payload(payload)
                    course_count = len({course["cc_code"] for course in courses if course["cc_code"]})
                    prior_year = data_year != req.year_id
                    goal_status["assist_url"] = goal_status["assist_url"] or build_assist_url(data_year, source_id, target.target_id, document_key)
                    goal_status["college_statuses"].append({
                        "college": source_name,
                        "status": "articulated" if course_count else "no_courses",
                        "data_year": data_year,
                        "is_prior_year": prior_year,
                        "assist_url": build_assist_url(data_year, source_id, target.target_id, document_key),
                        "course_count": course_count,
                        "courses": [
                            {
                                "course_code": item["cc_code"],
                                "course_name": item["cc_title"],
                                "target_course": item["target_code"],
                                "units": item["units"],
                                "is_series": item["is_series"],
                            }
                            for item in courses if item["cc_code"]
                        ],
                        "policy_notes": notes,
                        "series_rules": series_rules,
                    })
                    agreements.append({
                        "source_id": source_id,
                        "source_name": source_name,
                        "target_id": target.target_id,
                        "target_name": target.target_name,
                        "major": target.major,
                        "year_id": data_year,
                        "document_key": document_key,
                        "courses": [{"code": item["cc_code"], "title": item["cc_title"], "units": item["units"]} for item in courses if item["cc_code"]],
                        "payload": payload,
                        "series_rules": series_rules,
                        "notes": notes,
                    })
                else:
                    goal_status["college_statuses"].append({
                        "college": source_name,
                        "status": "not_in_database",
                        "data_year": None,
                        "is_prior_year": False,
                        "course_count": 0,
                    })
    finally:
        conn.close()
    if not agreements:
        raise HTTPException(status_code=404, detail="No saved agreement matches that selection. Choose a program listed in the selectors.")
    matrix_result = compute_overlap_matrix(agreements)
    deterministic_plan = build_transfer_plan(agreements, req.year_id, req.main_source_id or req.source_ids[0])
    fallback_courses = deterministic_plan["recommended_courses"]
    course_board = build_course_board(
        agreements=agreements,
        requested_year_id=req.year_id,
        source_ids=req.source_ids,
        main_source_id=req.main_source_id or req.source_ids[0],
    )
    board_courses = course_board["required"] + course_board["recommended"]
    for course in board_courses:
        course["supported_goals"] = [goal["label"] for goal in course["goals"]]
    deterministic_plan["recommended_courses"] = board_courses or fallback_courses
    deterministic_plan["course_board"] = course_board
    deterministic_plan["targets"] = goal_statuses
    deterministic_plan["coverage"]["selected_targets"] = len(goal_statuses)
    if deterministic_plan["recommended_courses"]:
        model_input = to_model_input(matrix_result, deterministic_plan)
        try:
            technical_plan = generate_technical_plan(model_input)
            summary = generate_student_summary(StudentSummaryInput(plan=technical_plan))
            technical_plan_data = technical_plan.model_dump(mode="json")
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    else:
        summary = "No articulated courses were found for these goals in the selected colleges or the saved prior-year fallback. Check the university-specific results and linked Assist agreements."
        technical_plan_data = {
            "summary": summary,
            "course_priorities": [],
            "warnings": deterministic_plan["warnings"],
            "source_urls": [],
        }
    return {"matrix": to_frontend_matrix(matrix_result), "series_rules": matrix_result["series_rules"], "total_targets": matrix_result["total_targets"], "summary": summary, "technical_plan": technical_plan_data, "plan": deterministic_plan, "isDemo": False}

@app.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        reply = answer_student_question(ChatInput(plan_context=req.plan_context, history=req.history, message=req.message))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return reply.model_dump()


# API routes are registered first. The same process can serve the website with
# same-origin cookies in hosting environments as well as the local launcher.
frontend_directory = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/chatbot", StaticFiles(directory=frontend_directory / "chatbot", html=True), name="deanza-chatbot")
app.mount("/", FrontendFiles(directory=frontend_directory, html=True), name="website")
