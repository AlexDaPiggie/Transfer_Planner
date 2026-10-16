# Pathway frontend

Start the local beta site from the project root with:

```powershell
.\frontend\run_local.ps1
```

Then open `http://localhost:8080`. To use a different port, run `.\frontend\run_local.ps1 -Port 8081`.

The launcher starts both the FastAPI backend and the website. `js/config.js` contains the API base URL and the demo-mode switch; live backend calls are enabled by default.
