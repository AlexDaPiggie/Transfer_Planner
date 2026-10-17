"""Verify email provider authentication without sending a message."""
import json
import os
import smtplib
import ssl

import requests
from dotenv import load_dotenv


def check():
    load_dotenv(".env")
    load_dotenv(".env.local", override=True)
    if os.getenv("BREVO_API_KEY") and os.getenv("BREVO_SENDER_EMAIL"):
        headers = {"api-key": os.environ["BREVO_API_KEY"], "accept": "application/json"}
        response = requests.get("https://api.brevo.com/v3/account", headers=headers, timeout=20)
        if response.status_code != 200:
            return {"provider": "brevo", "authenticated": False, "http_status": response.status_code, "emails_sent": 0}
        senders = requests.get("https://api.brevo.com/v3/senders", headers=headers, timeout=20)
        senders.raise_for_status()
        sender_ready = any(sender.get("email", "").lower() == os.environ["BREVO_SENDER_EMAIL"].strip().lower() and sender.get("active") for sender in senders.json().get("senders", []))
        return {"provider": "brevo", "authenticated": True, "sender_ready": sender_ready, "emails_sent": 0}
    sender = os.getenv("CAMPUS_COMPASS_EMAIL")
    password = os.getenv("CAMPUS_COMPASS_EMAIL_PASSWORD")
    if sender and password:
        with smtplib.SMTP_SSL(os.getenv("CAMPUS_COMPASS_SMTP_HOST", "smtp.gmail.com"), int(os.getenv("CAMPUS_COMPASS_SMTP_PORT", "465")), context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(sender, password)
        return {"provider": "smtp", "authenticated": True, "emails_sent": 0}
    return {"configured": False, "emails_sent": 0}


if __name__ == "__main__":
    try:
        result = check()
        print(json.dumps(result))
        if not result.get("authenticated") or result.get("sender_ready") is False:
            raise SystemExit(1)
    except Exception as exc:
        print(json.dumps({"email_check": "failed", "error_type": type(exc).__name__, "emails_sent": 0}))
        raise SystemExit(1)
