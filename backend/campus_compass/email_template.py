"""Compact Pathway email digest with all today events and five upcoming picks."""
from datetime import date, timedelta
from html import escape
from urllib.parse import urlsplit


def select_digest_events(events, current_date):
    end = current_date + timedelta(days=7)
    today_events, upcoming = [], []
    for event in events:
        try:
            day = date.fromisoformat(str(event.get("date") or "")[:10])
        except ValueError:
            continue
        if day == current_date:
            today_events.append(event)
        elif current_date < day <= end:
            upcoming.append(event)
    order = {"high": 0, "medium": 1, "low": 2}
    upcoming.sort(key=lambda event: (order.get(event.get("tier"), 3), str(event["date"])))
    picks = upcoming[:5]
    picks.sort(key=lambda event: str(event["date"]))
    return today_events, picks


def build_digest(events, profile, unsubscribe_url, current_date):
    today_events, upcoming = select_digest_events(events, current_date)
    sections = [("Today's events", today_events), ("Coming up in the next 7 days", upcoming)]
    text = ["Transfer Pathway | Campus Compass", current_date.strftime("%A, %B %d, %Y"), ""]
    content = []
    colors = {"high": "#E85A4F", "medium": "#D9922F", "low": "#5C7A93"}
    for heading, items in sections:
        text.extend([heading, ""])
        rows = []
        for event in items:
            title = str(event.get("title") or "Campus event")
            day = date.fromisoformat(str(event["date"])[:10])
            details = " | ".join(str(event[key]) for key in ("time", "location") if event.get(key))
            reason = str(event.get("reason") or "")
            tier = event.get("tier")
            color = colors.get(tier, "#9AA3AD")
            label = f"{tier.capitalize()} priority" if tier in colors else "Campus event"
            url = str(event.get("url") or "")
            try:
                if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).netloc:
                    url = ""
            except ValueError:
                url = ""
            title_html = escape(title)
            if url:
                title_html = f'<a href="{escape(url, quote=True)}" style="color:#172a3a;text-decoration:none">{title_html} <span style="color:#146c94">&rarr;</span></a>'
            text.extend([day.isoformat(), title, details, label, reason, url, ""])
            reason_html = f'<p style="margin:7px 0 0;color:#607386;font-size:12px;line-height:1.6">{escape(reason)}</p>' if reason else ""
            rows.append(f'''<tr><td style="padding:17px 0;border-bottom:1px solid #e5eef0;vertical-align:top;width:54px"><table role="presentation" cellspacing="0" cellpadding="0" width="43" style="background:#e5f5f1;border-radius:8px;text-align:center"><tr><td style="padding:7px 2px 2px;color:#147d73;font-size:9px;font-weight:700">{day.strftime('%b').upper()}</td></tr><tr><td style="padding:0 2px 7px;color:#172a3a;font-size:21px;font-weight:700">{day.day}</td></tr></table></td><td style="padding:17px 0;border-bottom:1px solid #e5eef0;vertical-align:top"><p style="margin:0 0 6px;font-size:15px;line-height:1.45;font-weight:600">{title_html}</p><p style="margin:0;color:#607386;font-size:12px;line-height:1.6">{escape(details)}</p>{reason_html}<p style="margin:7px 0 0;font-size:10px;color:#607386"><span style="color:{color}">&#9679;</span> {label}</p></td></tr>''')
        if not items:
            text.append("No events scheduled.")
            rows.append('<tr><td style="padding:16px 0;color:#607386;font-size:13px">No events scheduled.</td></tr>')
        note = "All of today's events" if heading == "Today's events" else "Up to 5 picks, selected by AI priority"
        content.append(f'<tr><td style="padding:25px 0 0"><h2 style="margin:0;color:#172a3a;font-size:18px;letter-spacing:-.3px">{heading} <span style="font-size:12px;font-weight:400;color:#607386">({len(items)})</span></h2><p style="margin:5px 0 0;color:#607386;font-size:11px">{note}</p><table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table></td></tr>')
    start = (current_date + timedelta(days=1)).strftime("%b %d")
    end = (current_date + timedelta(days=7)).strftime("%b %d")
    text.extend(["Turn off daily emails:", unsubscribe_url])
    html = f'''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><style>@media(max-width:480px){{.email-paper{{padding:22px 18px!important}}.email-outside{{padding:12px 8px!important}}}}</style></head><body style="margin:0;background:#f4fbfd;color:#172a3a;font-family:Arial,Helvetica,sans-serif"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">All today's events and five picks for the week ahead.</div><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4fbfd"><tr><td class="email-outside" align="center" style="padding:28px 12px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px"><tr><td style="padding:0 4px 17px;font-size:16px;font-weight:700;letter-spacing:-.5px">Transfer <span style="color:#146c94">Pathway</span><span style="font-size:10px;font-weight:400;letter-spacing:1px;color:#607386"> &nbsp; / &nbsp; CAMPUS COMPASS</span></td></tr><tr><td class="email-paper" style="padding:28px;background:#ffffff;border:1px solid #d4e4e9;border-top:3px solid #147d73;border-radius:10px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td><p style="margin:0 0 9px;color:#147d73;font-size:11px;letter-spacing:1px;font-weight:600">{current_date.strftime('%A, %B %d, %Y').upper()}</p><h1 style="margin:0 0 9px;font-size:27px;letter-spacing:-1px;line-height:1.2">Your campus briefing.</h1><p style="margin:0;color:#607386;font-size:13px;line-height:1.7">Today, plus a few things worth planning for.</p><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:20px;background:#edf7fa;border-radius:8px"><tr><td style="padding:13px 15px;font-size:12px;color:#146c94"><strong>{len(today_events)}</strong> today &nbsp;&middot;&nbsp; <strong>{len(upcoming)}</strong> upcoming picks</td></tr><tr><td style="padding:0 15px 13px;font-size:11px;color:#607386">Week ahead: {start} &ndash; {end}</td></tr></table></td></tr>{''.join(content)}</table></td></tr><tr><td style="padding:18px 10px;text-align:center;font-size:11px;line-height:1.8;color:#607386">Daily campus emails from Transfer Pathway.<br><a href="{escape(unsubscribe_url, quote=True)}" style="color:#146c94">Unsubscribe</a></td></tr></table></td></tr></table></body></html>'''
    return "\n".join(text), html
