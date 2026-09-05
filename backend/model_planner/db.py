import sqlite3 #manage database locally
import json #turn text to json (dict)
from typing import Any, Optional

DB_PATH = "transfer.db"

def get_agreement(
    year_id: int,
    source_id: int,
    target_id: int,
    major_name: str,
    db_path: str = DB_PATH
) -> Optional[dict[str, Any]]:

    """Direct Lookup for single articulation agreement."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT raw_payload FROM agreements
        WHERE year_id=? AND source_school_id=? AND target_school_id=? AND major_name=?
""", (year_id, source_id, target_id, major_name))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None
    