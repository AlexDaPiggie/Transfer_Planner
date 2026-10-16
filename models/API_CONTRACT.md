# Future FastAPI contract

`POST /api/generate-plan` accepts `{ "year_id": 75, "source_ids": [113], "targets": [] }` and returns a matrix, series rules, summary, and technical plan. `POST /api/chat` accepts `{ "plan_context": "...", "history": [], "message": "..." }` and returns `{ "reply": "..." }`.

Keep the OpenRouter key on the server. The browser must never receive it.
