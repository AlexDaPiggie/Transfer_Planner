"""Safe local setup checks. Prints status only, never database URLs or keys."""
import argparse
import json
import os
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply additive integration migrations")
    parser.add_argument("--warm-events", action="store_true", help="Fetch and cache public campus events")
    parser.add_argument("--smoke-ai", action="store_true", help="Rank up to three public events using an example profile")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.local", override=True)
    os.environ.setdefault("PGCONNECT_TIMEOUT", "10")
    target = urlsplit(os.getenv("DATABASE_URL", ""))
    if args.warm_events or args.smoke_ai:
        from .routes import load_events
        try:
            events = load_events()
            print(json.dumps({"cached_events": len(events)}))
            if args.smoke_ai:
                from .ranking import rank_events
                if not events:
                    raise RuntimeError("No events available")
                ranked = rank_events({"year": "freshman", "major": "Computer Science", "interests": []}, events[:3])
                print(json.dumps({"ai_ranked_events": len(ranked), "valid_tiers": all(e.get("tier") in ("high", "medium", "low") for e in ranked)}))
        except Exception as exc:
            print(json.dumps({"event_check": "failed", "error_type": type(exc).__name__}))
            raise SystemExit(1)
        return
    print(json.dumps({"database_target": {"host": target.hostname, "database": target.path.lstrip("/")}}))
    from scraper.sync_db import get_db_connection
    try:
        with closing(get_db_connection()) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pathway_users LIMIT 1")
            if args.apply:
                for filename in ("003_pathway_student_profiles.sql", "004_compass_account_features.sql"):
                    cur.execute((ROOT / "migrations" / filename).read_text(encoding="utf-8"))
                conn.commit()
            tables = {}
            for table in ("pathway_users", "pathway_student_profiles", "pathway_email_preferences", "pathway_password_resets"):
                cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)", (table,))
                tables[table] = bool(cur.fetchone()[0])
        print(json.dumps({"database": "connected", "migrations_applied": args.apply, "tables": tables}))
    except Exception as exc:
        print(json.dumps({"database": "unavailable", "error_type": type(exc).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
