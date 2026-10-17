# Transfer Planner + Campus Compass

Transfer Planner remains the main application and supplies the shared styling,
login session, account database, and navigation. The home page lets students
choose Transfer Planner or Campus Compass.

## Run locally

The additional packages and migrations 003/004 were installed/applied in this
workspace. On another machine, install the complete backend requirements and
apply the migrations to the authorized database:

```powershell
python -m pip install -r backend/requirements.txt
python -m backend.campus_compass.maintenance --apply
```

Start from the repository root:

```powershell
.\frontend\run_local.ps1
```

Open http://localhost:8080. Restart an already-running backend after code or
`.env.local` changes. The launcher detects older backends and asks you to stop
them before reuse. It prefers the project `.venv311` interpreter.

For hosting, the FastAPI application also serves the frontend and its assets
at its root. APIs then use the website origin. Set `PATHWAY_PUBLIC_URL`,
`PATHWAY_ALLOWED_ORIGINS`, `PATHWAY_ENV=production` and a persistent
`PATHWAY_SESSION_SECRET` for the real HTTPS domain. Keep `.env.local` private.

## Shared accounts and profiles

Both services use `/api/auth` and the same signed `pathway_session` cookie.
Campus profiles and email preferences are stored by the server-verified account
ID in PostgreSQL. Completed courses retain the existing account storage.
There were no existing Campus Compass members to migrate.

Password recovery is part of the common account dialog. Recovery links expire
after one hour and can be used once. Resetting a password invalidates previous
sessions in both services. Recovery requests return the same message for unknown
and known accounts, with a per-account request limit.

## Events and AI

The original Campus Compass scraping, geocoding, event identity, vocabulary and
ranking logic are reused. The original prompt is retained; provider selection
now defaults to Transfer Planner's existing `OPENROUTER_API_KEY` when available.
Set `CAMPUS_COMPASS_AI_PROVIDER=bedrock` to explicitly use the upstream AWS path.
`CAMPUS_COMPASS_AI_MODEL` can select a particular OpenRouter model; otherwise the
existing Transfer Planner fallback models are used.

A real scrape cached 147 public events in this workspace. Three were successfully
ranked with a sample profile. These checks do not guarantee every source responds;
some De Anza category pages timed out during the scrape.

The event cache is `backend/campus_compass/events.db` and should use durable
storage when deployed. A running backend checks hourly and refreshes data that
is at least six hours old. Failed refreshes retain the previous snapshot.
Leaflet 1.9.4 assets and license are bundled locally under
`frontend/vendor/leaflet`; OpenStreetMap tiles still need internet access.

## Daily event emails

Email supports Brevo or SMTP. Copy settings names from `.env.example`; never
paste secrets into a tracked file. SMTP authentication was verified using the
local settings. No real email has been sent by the integration checks.

A student opts in using the Campus Compass checkbox, and the account is immediately subscribed. No confirmation email or link is required. The daily
message includes every event today and up to five upcoming events from the following seven calendar days, selected by AI priority,
with an unsubscribe link. No message is sent when there are no events today. Preferences and delivery claims live in the shared
PostgreSQL database. One claim per account/day prevents duplicate delivery by
multiple app workers. Failed or uncertain deliveries are not retried automatically.

The local configuration enables scheduling at 09:00 America/Los_Angeles. Keep
the backend running for scheduled delivery. Set
`PATHWAY_DAILY_EMAILS_ENABLED=false` to disable scheduling. Changing settings
requires restarting the backend. The CLI previews eligible recipient counts
without sending; `--send` explicitly performs delivery:

```powershell
python -m backend.campus_compass.daily_email
```

## Verification

```powershell
python -m pytest tests -q
node --test frontend/tests/*.test.mjs
python frontend/tests/browser_smoke.py
python -m backend.campus_compass.check_email
python -m backend.campus_compass.smoke_accounts
```

Browser checks use fake APIs and example.invalid accounts. The DB smoke check
uses one rolled-back transaction and a captured email transport, so it leaves no
test users or delivered emails. Public event/AI verification is available through
`python -m backend.campus_compass.maintenance --warm-events --smoke-ai`.

No deployment or Git push was performed. Source attribution and upstream revision
are in `backend/campus_compass/UPSTREAM.md`; the MIT license is preserved there.

## Goal buttons

What are you looking for? offers exactly three optional multi-select goals:
Transfer, Career & Scholarships, and Campus Life. Major handles academic-field
personalization. Transfer immediately toggles transfer-event visibility; Save
and recommend persists selections and updates AI priorities. Previous predefined
categories merge into the corresponding broader goals without adding buttons.
No academic-year or preparation-stage selector is shown.

Email opt-in now activates immediately for the signed-in account. Existing pending requests are shown as off; turn the checkbox on once to activate them. Email verification is no longer a delivery condition. Tests never send actual messages.

The email uses a compact briefing layout: one white panel, small date blocks, thin separators, and linked titles. No large hero banner or individual event buttons. The upcoming cap is applied in the shared renderer so design test emails follow the same all-today-plus-five rule.
