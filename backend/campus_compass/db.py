"""Shared SQLite event cache only; account data lives in Pathway PostgreSQL."""

import json
import sqlite3
from datetime import datetime, timezone
from .config import DB_PATH
from .event_identity import event_identity


# ---------------------------------------------------------
# Events
# ---------------------------------------------------------

EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date TEXT,
    time TEXT,
    location TEXT,
    category TEXT,
    source TEXT,
    description TEXT,
    url TEXT,
    latitude REAL,
    longitude REAL,
    is_virtual INTEGER NOT NULL DEFAULT 0,
    match_type TEXT,
    scraped_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """
    Open the Campus Compass SQLite database and make sure
    all required tables exist.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute(EVENTS_SCHEMA)
    conn.execute("CREATE TABLE IF NOT EXISTS cache_metadata (id INTEGER PRIMARY KEY, scraped_at TEXT NOT NULL)")

    return conn


# =========================================================
# EVENT FUNCTIONS
# =========================================================

def _event_id(ev: dict) -> str:
    """
    Primary key for an event row.

    Delegates to event_identity.event_identity() so storage uses exactly
    the same notion of "same event" that scraping de-duplicates on.
    """

    return event_identity(ev)


def save_events(events: list[dict], scraped_at: str) -> None:
    """
    Replace the current event dataset with a fresh scrape.

    INSERT OR REPLACE rather than INSERT: scraping already de-duplicates
    via event_identity(), but a storage-layer crash is a bad way to find
    out about a new duplicate-shaped source. Last write wins.
    """

    conn = get_connection()

    with conn:
        conn.execute("DELETE FROM events")
        conn.execute("INSERT OR REPLACE INTO cache_metadata (id, scraped_at) VALUES (1, ?)", (scraped_at,))

        conn.executemany(
            """
            INSERT OR REPLACE INTO events (
                event_id,
                title,
                date,
                time,
                location,
                category,
                source,
                description,
                url,
                latitude,
                longitude,
                is_virtual,
                match_type,
                scraped_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    _event_id(ev),
                    ev.get("title"),
                    ev.get("date"),
                    ev.get("time"),
                    ev.get("location"),
                    ev.get("category"),
                    ev.get("source", "deanza_events"),
                    ev.get("description"),
                    ev.get("url"),
                    ev.get("latitude"),
                    ev.get("longitude"),
                    1 if ev.get("is_virtual") else 0,
                    ev.get("match_type"),
                    scraped_at,
                )
                for ev in events
            ],
        )

    conn.close()


def load_events() -> list[dict] | None:
    """
    Load all scraped events.

    Returns None when the database has not been populated yet.
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM events
        ORDER BY date IS NULL, date
        """
    ).fetchall()

    conn.close()

    if not rows:
        return [] if last_scraped_at() else None

    events = []

    for row in rows:
        ev = dict(row)
        ev["is_virtual"] = bool(ev["is_virtual"])
        events.append(ev)

    return events


def last_scraped_at():
    conn = get_connection()
    try:
        row = conn.execute("SELECT scraped_at FROM cache_metadata WHERE id = 1").fetchone()
        if not row:
            row = conn.execute("SELECT MAX(scraped_at) FROM events").fetchone()
        return row[0] if row else None
    finally:
        conn.close()
