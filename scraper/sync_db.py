import psycopg2
import json #convert text -> json (dict)
import os
import re
from dotenv import load_dotenv

DB_PATH = "transfer.db"
load_dotenv()

def normalize_database_url(db_url: str) -> str:
    """Remove accidental quotes around URL option values from environment files."""
    return re.sub(r"(sslmode=)[\"']?([^&\s\"']+)[\"']?", r"\1\2", db_url).strip()

def get_db_connection():
    """Get the URL link of the remote database to connect"""
    db_url = os.getenv("DATABASE_URL")
    #in case the url of the database platform is not provided
    if not db_url:
        raise ValueError("Missing DATABASE_URL in .env file")
    db_url = normalize_database_url(db_url)
    cert_path = "/root/.postgresql/root.crt"
    if os.path.exists(cert_path):
        return psycopg2.connect(db_url, sslrootcert=cert_path)
    elif os.path.exists("root.crt"):
        return psycopg2.connect(db_url, sslrootcert="root.crt")
    return psycopg2.connect(db_url)

def init_db (db_path: str = DB_PATH):
    """This function is to initialize the database"""
    conn = get_db_connection()
    cur = conn.cursor()
    """
    The SQL block below is to create a new table to store the information.
    1/ Check if the table exists
    2/ automatically increment the id key for every row
    3/ store the basic numbers identifying year, cc, and uni
    4/ store the name, the "unique key" for every udpate(to check for changes between the databse and assist.org)
    5/ store the raw json content from the course requirements.
    """
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agreements(
        id SERIAL PRIMARY KEY,
        year_id INTEGER NOT NULL,
        source_school_id INTEGER NOT NULL,
        target_school_id INTEGER NOT NULL,
        major_name TEXT NOT NULL,
        document_key TEXT NOT NULL,
        raw_json JSONB,
        UNIQUE(year_id, source_school_id, target_school_id, major_name)
        )
""")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS institutions(
        institution_id INTEGER PRIMARY KEY,
        institution_name TEXT NOT NULL,
        is_community_college BOOLEAN NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
""")
    #Save the changes and close the table
    conn.commit()
    conn.close()

def save_institutions(institutions: list[dict]) -> None:
    """Cache Assist institution names so the web app never has to display opaque IDs."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS institutions(
        institution_id INTEGER PRIMARY KEY,
        institution_name TEXT NOT NULL,
        is_community_college BOOLEAN NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    for institution in institutions:
        names = institution.get("names") or []
        name = next((item.get("name") for item in names if item.get("name")), None)
        if not name or institution.get("id") is None:
            continue
        cur.execute("""
            INSERT INTO institutions (institution_id, institution_name, is_community_college, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (institution_id) DO UPDATE SET
                institution_name = EXCLUDED.institution_name,
                is_community_college = EXCLUDED.is_community_college,
                updated_at = NOW()
        """, (institution["id"], name, bool(institution.get("isCommunityCollege", False))))
    conn.commit()
    conn.close()

def save_agreement(
    year_id: int,
    source_id: int,
    target_id: int,
    major_name: str, 
    document_key: str,
    detail: dict,
):

    """This is to save/udpate an agreement in the database"""
    conn = get_db_connection()
    cur = conn.cursor()

    """
    The below block writes a new row in the table. If the row already exists, it updates the old row with the new one instead of crashing the row (ON CONFLICT...)

    Note: EXCLUDED is the new data trying to be inserted. The new and old data are tracked by ids.
    """
    cur.execute("""
        INSERT INTO agreements (year_id, source_school_id, target_school_id, major_name, document_key, raw_json)
        VALUES(%s, %s, %s, %s, %s, %s)
        ON CONFLICT (year_id, source_school_id, target_school_id, major_name)
        DO UPDATE SET
            raw_json = EXCLUDED.raw_json,
            document_key = EXCLUDED.document_key;
""", (year_id, source_id, target_id, major_name, document_key, json.dumps(detail)))

    #Update and close the database
    conn.commit()
    conn.close()
