from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import json
from backend.model_planner.matrix_engine import compute_overlap_matrix

app = FastAPI(title = "Transfer Educational Plan AI Assistant", version = "1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=[
        'http://localhost:5500',
        'http://127.0.0.1:5500',
        'https://educational-plan-chatbot.vercel.app',
    ]
)

DB_PATH = "transfer.db"
class TargetSelection (BaseModel):
    target_id: int
    target_name: str
    major: str

class PlanRequest(BaseModel):
    year_id: int
    source_ids: list[int]
    targets: list[TargetSelection]

@app.post("/api/generate-plan")
def api_generate_plan(req: PlanRequest):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    agreements = []

    for src_id in req.source_ids:
        for tgt in req.targets:
            cur.execute("""
                SELECT raw_payload FROM agreements
                WHERE year_id=? AND source_school_id=? AND
                target_school_id=? AND major_name=?
            """, (req.year_id, src_id, tgt.target_id, tgt.major))

            row = cur.fetchone()
            if row:
                agreements.append({
                    "target_school_name": tgt.target_name,
                    "payload": json.loads(row[0])
                })
    conn.close()

    if not agreements:
        raise HTTPException(status_code=404, detail = "No agreements found in databse.")

    matrix_res = compute_overlap_matrix(agreements)
    return {
        "matrix": matrix_res["matrix"],
        "series_rules": matrix_res["series_rules"],
        "total_targets": matrix_res["total_targets"],
    }