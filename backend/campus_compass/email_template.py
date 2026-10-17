"""Compact De Anza Guide email digest with all today events and five upcoming picks."""
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
    text = ["De Anza Guide | De Anza Events", current_date.strftime("%A, %B %d, %Y"), ""]
    content = []
    colors = {"high": "#8a1538", "medium": "#a65b24", "low": "#176b55"}
    for heading, items in sections:
        text.extend([heading, ""])
        rows = []
        for event in items:
            title = str(event.get("title") or "Campus event")
            day = date.fromisoformat(str(event["date"])[:10])
            details = " | ".join(str(event[key]) for key in ("time", "location") if event.get(key))
            tier = event.get("tier")
            color = colors.get(tier, "#64748b")
            label = f"{tier.capitalize()} priority" if tier in colors else "Campus event"
            url = str(event.get("url") or "")
            try:
                if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).netloc:
                    url = ""
            except ValueError:
                url = ""
            title_html = escape(title)
            if url:
                title_html = f'<a href="{escape(url, quote=True)}" style="color:#172033;text-decoration:none">{title_html} <span style="color:#8a1538">&rarr;</span></a>'
            text.extend([day.isoformat(), title, details, label, url, ""])
            rows.append(f'''<tr><td class="email-divider" style="padding:17px 0;border-bottom:1px solid #eadde2;vertical-align:top;width:54px"><table role="presentation" cellspacing="0" cellpadding="0" width="43" class="email-tint" style="background:#fff0f4;border-radius:8px;text-align:center"><tr><td style="padding:7px 2px 2px;color:#8a1538;font-size:9px;font-weight:700">{day.strftime('%b').upper()}</td></tr><tr><td style="padding:0 2px 7px;color:#172033;font-size:21px;font-weight:700">{day.day}</td></tr></table></td><td class="email-divider" style="padding:17px 0;border-bottom:1px solid #eadde2;vertical-align:top"><p style="margin:0 0 6px;font-size:15px;line-height:1.45;font-weight:600">{title_html}</p><p style="margin:0;color:#64748b;font-size:12px;line-height:1.6">{escape(details)}</p><p style="margin:7px 0 0;font-size:10px;color:#64748b"><span style="color:{color}">&#9679;</span> {label}</p></td></tr>''')
        if not items:
            text.append("No events scheduled.")
            rows.append('<tr><td style="padding:16px 0;color:#64748b;font-size:13px">No events scheduled.</td></tr>')
        content.append(f'<tr><td style="padding:25px 0 0"><h2 style="font-family:Georgia,Times,serif;margin:0;color:#172033;font-size:18px;letter-spacing:-.3px">{heading} <span style="font-size:12px;font-weight:400;color:#64748b">({len(items)})</span></h2><table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table></td></tr>')
    start = (current_date + timedelta(days=1)).strftime("%b %d")
    end = (current_date + timedelta(days=7)).strftime("%b %d")
    text.extend(["Turn off daily emails:", unsubscribe_url])
    html = f'''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><style>:root{{color-scheme:light dark;supported-color-schemes:light dark}}@media(prefers-color-scheme:dark){{body,.email-background{{background:#151018!important;color:#f7f1f3!important}}.email-paper{{background:#211924!important;border-color:#49333f!important;border-top-color:#ff8aaa!important}}td,h1,h2{{color:#f7f1f3!important}}p,span{{color:#c9bbc2!important}}a,a span,.email-accent{{color:#ff8aaa!important}}.email-tint{{background:#33212e!important;color:#ff8aaa!important}}.email-divider{{border-bottom-color:#49333f!important}}}}@media(max-width:480px){{.email-paper{{padding:22px 18px!important}}.email-outside{{padding:12px 8px!important}}}}</style></head><body style="margin:0;background:#fff8fa;color:#172033;font-family:Arial,Helvetica,sans-serif"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">All today's events and five picks for the week ahead.</div><table role="presentation" width="100%" cellspacing="0" cellpadding="0" class="email-background" style="background:#fff8fa"><tr><td class="email-outside" align="center" style="padding:28px 12px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px"><tr><td style="padding:0 4px 17px;font-size:16px;font-weight:700;letter-spacing:-.5px">De Anza <span style="color:#8a1538">Guide</span><span style="font-size:10px;font-weight:400;letter-spacing:1px;color:#64748b"> &nbsp; / &nbsp; DE ANZA EVENTS</span></td></tr><tr><td class="email-paper" style="padding:28px;background:#ffffff;border:1px solid #eadde2;border-top:3px solid #8a1538;border-radius:10px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td><p style="margin:0 0 9px;color:#8a1538;font-size:11px;letter-spacing:1px;font-weight:600">{current_date.strftime('%A, %B %d, %Y').upper()}</p><h1 style="font-family:Georgia,Times,serif;margin:0 0 9px;font-size:27px;letter-spacing:-1px;line-height:1.2">Your campus briefing.</h1><table role="presentation" width="100%" cellspacing="0" cellpadding="0" class="email-tint" style="margin-top:20px;background:#fff0f4;border-radius:8px"><tr><td style="padding:13px 15px;font-size:12px;color:#8a1538"><strong>{len(today_events)}</strong> today &nbsp;&middot;&nbsp; <strong>{len(upcoming)}</strong> upcoming picks</td></tr><tr><td style="padding:0 15px 13px;font-size:11px;color:#64748b">Week ahead: {start} &ndash; {end}</td></tr></table></td></tr>{''.join(content)}</table></td></tr><tr><td style="padding:18px 10px;text-align:center;font-size:11px;line-height:1.8;color:#64748b">Daily campus emails from De Anza Guide.<br><a href="{escape(unsubscribe_url, quote=True)}" style="color:#8a1538">Unsubscribe</a></td></tr></table></td></tr></table></body></html>'''
    return "\n".join(text), html
