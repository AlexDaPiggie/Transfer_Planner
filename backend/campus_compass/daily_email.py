"""Daily opt-in emails. CLI previews by default; --send explicitly delivers."""
import argparse
import asyncio
import json
import logging
import os
from contextlib import closing
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor

from scraper.sync_db import get_db_connection
from . import mailer
from .email_template import build_digest
from .notifications import unsubscribe_token

logger = logging.getLogger(__name__)


def today():
    return datetime.now(ZoneInfo(os.getenv("DAILY_EMAIL_TIMEZONE", "America/Los_Angeles"))).date()


def weekly_events(events, current_date):
    """Today's events plus the following seven calendar days, regardless of weekday."""
    end = current_date + timedelta(days=7)
    selected = []
    for event in events:
        try:
            event_date = date.fromisoformat(str(event.get("date") or "")[:10])
        except ValueError:
            continue
        if current_date <= event_date <= end:
            selected.append(event)
    return selected


def build_email(events, profile, unsubscribe_url, current_date=None):
    return build_digest(events, profile, unsubscribe_url, current_date or today())


def run_delivery(*, send=False, recipient=None):
    if send and not mailer.configured():
        raise RuntimeError("Email delivery is not configured")
    current_date = today()
    with closing(get_db_connection()) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT u.user_id, u.email, p.year, p.major, p.interests FROM pathway_users u "
            "JOIN pathway_email_preferences e ON e.user_id = u.user_id "
            "LEFT JOIN pathway_student_profiles p ON p.user_id = u.user_id "
            "WHERE e.daily_events = TRUE "
            "AND NOT EXISTS (SELECT 1 FROM pathway_email_deliveries d WHERE d.user_id = u.user_id AND d.delivery_date = %s)"
            + (" AND LOWER(u.email) = %s" if recipient else ""),
            (current_date, recipient.strip().lower()) if recipient else (current_date,),
        )
        subscribers = cur.fetchall()
    result = {"subscribers": len(subscribers), "sent": 0, "skipped": 0, "failed": 0, "preview": not send}
    if not subscribers or not send:
        return result
    from .routes import load_events
    from .ranking import rank_events
    events = weekly_events(load_events(), current_date)
    if not any(str(event.get("date") or "")[:10] == current_date.isoformat() for event in events):
        result["skipped"] = len(subscribers)
        return result
    for subscriber in subscribers:
        uid = subscriber["user_id"]
        try:
            profile = {"transfer_stage": "", "major": subscriber["major"] or "", "interests": subscriber["interests"] or []}
            ranked = rank_events(profile, events)
            ranked.sort(key=lambda event: str(event.get("date") or ""))
            link = f"{mailer.app_url()}/?service=compass#unsubscribe={unsubscribe_token(uid)}"
            text, html = build_email(ranked, profile, link, current_date)
            # A unique (user, day) claim prevents duplicate sends from concurrent
            # servers. A failed/uncertain send is never retried automatically.
            with closing(get_db_connection()) as conn, conn.cursor() as cur:
                cur.execute("SELECT daily_events FROM pathway_email_preferences WHERE user_id = %s FOR UPDATE", (uid,))
                if not cur.fetchone()[0]:
                    result["skipped"] += 1
                    continue
                cur.execute("INSERT INTO pathway_email_deliveries (user_id, delivery_date) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING user_id", (uid, current_date))
                claimed = cur.fetchone()
                conn.commit()
            if not claimed:
                result["skipped"] += 1
                continue
            try:
                mailer.send_email(subscriber["email"], f"Your Pathway campus events · {current_date.isoformat()}", text, html)
                state = "sent"
                result["sent"] += 1
            except Exception as exc:
                state = "failed"
                result["failed"] += 1
                logger.error("Daily email failed (%s)", type(exc).__name__)
            with closing(get_db_connection()) as conn, conn.cursor() as cur:
                cur.execute("UPDATE pathway_email_deliveries SET status = %s WHERE user_id = %s AND delivery_date = %s", (state, uid, current_date))
                conn.commit()
        except Exception as exc:
            result["failed"] += 1
            logger.error("Daily email preparation failed (%s)", type(exc).__name__)
    return result


async def delivery_loop():
    """The database claim makes scheduling safe across multiple app workers."""
    last_attempt = None
    while True:
        try:
            now = datetime.now(ZoneInfo(os.getenv("DAILY_EMAIL_TIMEZONE", "America/Los_Angeles")))
            scheduled = os.getenv("DAILY_EMAIL_TIME", "09:00")
            if mailer.configured() and now.strftime("%H:%M") >= scheduled and last_attempt != now.date():
                last_attempt = now.date()
                await asyncio.to_thread(run_delivery, send=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Daily email scheduler failed (%s)", type(exc).__name__)
        await asyncio.sleep(60)


def main():
    from dotenv import load_dotenv
    load_dotenv(".env")
    load_dotenv(".env.local", override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--email", help="Only preview or send to this subscriber")
    args = parser.parse_args()
    try:
        print(json.dumps(run_delivery(send=args.send, recipient=args.email)))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
