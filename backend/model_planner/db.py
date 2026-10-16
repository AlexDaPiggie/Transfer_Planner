import json #turn text to json (dict)
from typing import Any, Optional
from scraper.sync_db import get_db_connection

def get_agreement(
    year_id: int,
    source_id: int,
    target_id: int,
    major_name: str,
) -> Optional[dict[str, Any]]:

    """Direct Lookup for single articulation agreement."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT raw_json FROM agreements
        WHERE year_id=%s AND source_school_id=%s AND target_school_id=%s AND major_name=%s
""", (year_id, source_id, target_id, major_name))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None
