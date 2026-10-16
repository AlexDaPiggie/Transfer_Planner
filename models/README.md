# Transfer Planner models

These modules are intentionally independent from the current backend. Install `pip install -r models/requirements.txt`, set `OPENROUTER_API_KEY` in the environment, then import `generate_technical_plan`, `generate_student_summary`, or `answer_student_question`.

Model 1 creates a technical plan from verified matrix data. Model 2 creates student-facing explanations and chat replies from that plan. Prompts prohibit invented requirements and sources; callers must only supply verified agreement data.
