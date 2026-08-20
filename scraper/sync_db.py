import sqlite3 #mange local database
import json #convert text -> json (dict)
from typing import Any

DB_PATH = "transfer.db"

def init_db (db_path: str = DB_PATH):
    """To init SQLite db with required tables and indexes"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agreements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year_id INTEGER NOT NULL,
        source_school_id INTEGER NOT NULL,
        target_school_id INTEGER NOT NULL,
        major_name TEXT NOT NULL,
        raw_payload TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(year_id, source_school_id, target_school_id, major_name)
        )
""")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_agreement_lookup
        ON agreements(year_id, source_school_id, target_school_id, major_name)
""")
    conn.commit()
    conn.close()

def save_agreement(
    year_id: int,
    source_id: int,
    target_id: int,
    major_name: str, 
    payload: dict[str, Any],
    db_path: str = DB_PATH
):

    """This is to save/udpate an agreement JSON in sqlite"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO agreements (year_id, source_school_id, target_school_id, major_name, raw_payload)
        VALUES(?, ?, ?, ?, ?)
""", (year_id, source_id, target_id, major_name, json.dumps(payload)))
    conn.commit()
    conn.close()