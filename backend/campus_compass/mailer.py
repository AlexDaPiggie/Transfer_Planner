"""Shared email transport for account recovery and campus notifications."""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)


def configured():
    if os.getenv("BREVO_API_KEY") and os.getenv("BREVO_SENDER_EMAIL"):
        return True
    return bool(os.getenv("CAMPUS_COMPASS_EMAIL") and os.getenv("CAMPUS_COMPASS_EMAIL_PASSWORD"))


def app_url():
    url = os.getenv("PATHWAY_PUBLIC_URL", "http://localhost:8080").rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError("PATHWAY_PUBLIC_URL must be an absolute website URL")
    return url


def send_email(recipient, subject, text, html=None):
    """Called only by explicit account flows or the opt-in delivery command."""
    html = html or f"<p>{escape(text).replace(chr(10), '<br>')}</p>"
    if os.getenv("BREVO_API_KEY") and os.getenv("BREVO_SENDER_EMAIL"):
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": os.environ["BREVO_API_KEY"], "accept": "application/json"},
            json={
                "sender": {"name": os.getenv("BREVO_SENDER_NAME", "Transfer Pathway"), "email": os.environ["BREVO_SENDER_EMAIL"]},
                "to": [{"email": recipient}], "subject": subject,
                "textContent": text, "htmlContent": html,
            },
            timeout=20,
        )
        response.raise_for_status()
        return
    sender = os.getenv("CAMPUS_COMPASS_EMAIL")
    password = os.getenv("CAMPUS_COMPASS_EMAIL_PASSWORD")
    if not sender or not password:
        raise RuntimeError("Email delivery is not configured")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL(os.getenv("CAMPUS_COMPASS_SMTP_HOST", "smtp.gmail.com"), int(os.getenv("CAMPUS_COMPASS_SMTP_PORT", "465")), context=ssl.create_default_context(), timeout=20) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)


def deliver_account_message(recipient, subject, text):
    try:
        send_email(recipient, subject, text)
    except Exception as exc:
        # Provider exception text can contain email addresses or request payloads.
        logger.error("Account email delivery failed (%s)", type(exc).__name__)
