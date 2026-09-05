import psycopg2
import json #convert text -> json (dict)
import os
from dotenv import load_dotenv

DB_PATH = "transfer.db"
load_dotenv(override=True)

def get_db_connection():
    """Get the URL link of the remote database to connect"""
    db_url = os.getenv("DATABASE_URL")
    #in case the url of the database platform is not provided
    if not db_url:
        raise ValueError("Missing DATABASE_URL in .env file")
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
    #Save the changes and close the table
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