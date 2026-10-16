"""FastAPI boundary between the browser, verified agreement data, and AI models."""
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.model_planner.matrix_engine import compute_overlap_matrix, extract_courses_from_payload
from backend.model_planner.transfer_plan import build_assist_url, build_transfer_plan
from models.src.explainer import answer_student_question, generate_student_summary
from models.src.planner import generate_technical_plan
from models.src.schemas import ChatInput, StudentSummaryInput, TechnicalPlanInput
from scraper.sync_db import get_db_connection

app = FastAPI(title="Transfer Educational Plan AI Assistant", version="2.0.0")
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
                WHERE a.year_id=%s
            ) AS sources
            ORDER BY institution_name NULLS LAST, source_school_id""", (year_id,))
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
                WHERE a.year_id=%s AND a.source_school_id = ANY(%s)
            ) AS targets
            ORDER BY institution_name NULLS LAST, target_school_id""", (year_id, ids))
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
        cur.execute("SELECT DISTINCT major_name FROM agreements WHERE year_id=%s AND source_school_id = ANY(%s) AND target_school_id=%s ORDER BY major_name", (year_id, ids, target_id))
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
                cur.execute("SELECT raw_json, document_key FROM agreements WHERE year_id=%s AND source_school_id=%s AND target_school_id=%s AND major_name=%s", (req.year_id, source_id, target.target_id, target.major))
                row = cur.fetchone()
                goal_status = next(item for item in goal_statuses if item["target_id"] == target.target_id and item["major"] == target.major)
                source_name = label_school(source_id, "Community college")
                if row:
                    payload = decode_payload(row[0])
                    courses, series_rules, notes = extract_courses_from_payload(payload)
                    course_count = len({course["cc_code"] for course in courses if course["cc_code"]})
                    goal_status["assist_url"] = goal_status["assist_url"] or build_assist_url(req.year_id, source_id, target.target_id, row[1])
                    goal_status["college_statuses"].append({
                        "college": source_name,
                        "status": "articulated" if course_count else "no_courses",
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
                        "document_key": row[1],
                        "courses": [{"code": item["cc_code"], "title": item["cc_title"], "units": item["units"]} for item in courses if item["cc_code"]],
                        "payload": payload,
                        "series_rules": series_rules,
                        "notes": notes,
                    })
                else:
                    goal_status["college_statuses"].append({
                        "college": source_name,
                        "status": "not_in_database",
                        "course_count": 0,
                    })
    finally:
        conn.close()
    if not agreements:
        raise HTTPException(status_code=404, detail="No saved agreement matches that selection. Choose a program listed in the selectors.")
    matrix_result = compute_overlap_matrix(agreements)
    deterministic_plan = build_transfer_plan(agreements, req.year_id, req.main_source_id or req.source_ids[0])
    deterministic_plan["targets"] = goal_statuses
    deterministic_plan["coverage"]["selected_targets"] = len(goal_statuses)
    model_input = to_model_input(matrix_result, deterministic_plan)
    try:
        technical_plan = generate_technical_plan(model_input)
        summary = generate_student_summary(StudentSummaryInput(plan=technical_plan))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"matrix": to_frontend_matrix(matrix_result), "series_rules": matrix_result["series_rules"], "total_targets": matrix_result["total_targets"], "summary": summary, "technical_plan": technical_plan.model_dump(mode="json"), "plan": deterministic_plan, "isDemo": False}

@app.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        reply = answer_student_question(ChatInput(plan_context=req.plan_context, history=req.history, message=req.message))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return reply.model_dump()
