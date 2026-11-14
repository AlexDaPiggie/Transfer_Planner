# De Anza Guide integration

The home page offers Transfer Planner and De Anza Chatbot. Planner accounts and
completed courses use the existing PostgreSQL database and signed
`pathway_session` cookie.

## Run locally

Install backend dependencies, then start from the repository root:

```powershell
python -m pip install -r backend/requirements.txt
.\frontend\run_local.ps1
```

Open http://localhost:8080. The launcher prefers `.venv311` and checks API routes
before reusing a backend. Restart an already-running backend after code or
`.env.local` changes to load the current APIs and stop retired background jobs.

FastAPI serves the frontend and chatbot at its root. For hosting, set
`PATHWAY_PUBLIC_URL`, `PATHWAY_ALLOWED_ORIGINS`, `PATHWAY_ENV=production` and a
persistent `PATHWAY_SESSION_SECRET` for the HTTPS domain. Keep `.env.local` private.

On Render, set `DATABASE_URL` in the web service's Environment settings to the
active Planner PostgreSQL connection URL. Local `.env` files are ignored by Git
and are not deployed. Set `DEANZA_CHAT_DATABASE_URL` separately for the chatbot;
it is not a replacement for the Planner database. Redeploy after configuration
changes. A healthy `/api/health` response confirms the process is running, not
that its database is reachable: also verify `/api/catalog/sources?year_id=77`.

The catalog returns 503 with `database_not_configured` when `DATABASE_URL` is
missing, or `database_unavailable` when the database rejects the connection.
Server logs distinguish missing settings from a connection or missing-cluster
error without printing credentials. Restore the database connection, then use
the Planner's retry button to reload school choices without clearing saved plans.

## Accounts

Authentication uses `/api/auth`; completed courses use `/api/completed-courses`.
Email/password signup, login, Google sign-in and logout remain available.
Email delivery and email-based password recovery have been removed, including
recovery links, API endpoints, the recovery button, and sender configuration.
Email addresses are still used as account identifiers.

Apply the SQL files in `migrations/` in numerical order for a new database.
Migrations 001/002 create accounts and completed-course storage; 004 adds the
session version required by authentication. Retired profile, notification and
password-reset schema definitions have been removed. Existing PostgreSQL tables
and account/course data are unchanged. The local event cache and development
artifacts for retired features have been deleted.

The retired events service has no page, API routes, collection jobs, AI ranking,
map assets, or scheduled email delivery. Old service query links open the home
page. Restart the backend to stop jobs from an older running version.

## Verification

```powershell
python -m pytest tests models/tests -q
node --test frontend/tests/*.test.mjs
python frontend/tests/browser_smoke.py
python frontend/tests/browser_smoke.py --services-only
```

Browser checks use mocked APIs and example.invalid accounts. They cover service
navigation, account login/logout, planner layout, completed-course controls,
mobile width and login/signup controls without sending email.
