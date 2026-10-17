# Pathway frontend

Start the local beta site from the project root with:

```powershell
.\frontend\run_local.ps1
```

Then open `http://localhost:8080`. To use a different port, run `.\frontend\run_local.ps1 -Port 8081`.

The launcher starts both the FastAPI backend and the website. `js/config.js` contains the API base URL and the demo-mode switch; live backend calls are enabled by default.

The home page now offers Transfer Planner and De Anza Events. See
[`../INTEGRATION.md`](../INTEGRATION.md) for the additional event dependencies,
student-profile database migration, and AI recommendation setup. Restart an
already-running backend after updating the code to load the new API routes.

If this project's FastAPI backend is already running on port 8000, the launcher reuses it and leaves it running when you stop the website. If another service occupies port 8000, stop that service before launching.
