# Capped OpenRouter benchmark

Run `python -m models.benchmark.run --live` only when you want billable tests. The runner gets current catalog pricing, estimates each request before sending it, skips requests that could exceed the fixed $2 cap, and writes `results.json`. Then run `python -m models.benchmark.report` for a compact recommendation report.
