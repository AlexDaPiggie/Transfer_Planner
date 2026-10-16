"""Run a deliberately small, capped OpenRouter comparison. Never logs the API key."""
import argparse
import json
import os
import time
from pathlib import Path
from openai import OpenAI
from models.src.prompts import build_planner_messages
from models.src.schemas import TechnicalPlan, TechnicalPlanInput

BUDGET_USD = 2.0
CANDIDATES = ["google/gemini-2.5-flash", "openai/gpt-4o-mini", "mistralai/mistral-small-24b-instruct-2501", "google/gemini-2.5-flash-lite"]

def estimate_cost(prompt_tokens: int, completion_tokens: int, input_per_million: float, output_per_million: float) -> float:
    return (prompt_tokens * input_per_million + completion_tokens * output_per_million) / 1_000_000

def can_spend(spent: float, next_cost: float, budget: float = BUDGET_USD) -> bool:
    return spent + next_cost <= budget

def recommend(rows: list[dict]) -> dict[str, str | None]:
    valid = [row for row in rows if row.get("valid")]
    ranked = sorted(valid, key=lambda row: (row["estimated_cost"], row["latency_ms"]))
    return {"primary": ranked[0]["model"] if ranked else None, "fallback": ranked[1]["model"] if len(ranked) > 1 else None}

def model_prices() -> dict[str, tuple[float, float]]:
    """Read current catalog prices rather than baking mutable prices into source."""
    import urllib.request
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20) as response:
        catalog = json.load(response)["data"]
    return {item["id"]: (float(item["pricing"]["prompt"]) * 1_000_000, float(item["pricing"]["completion"]) * 1_000_000) for item in catalog}

def run() -> list[dict]:
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY is required for the live benchmark.")
    prices = model_prices()
    fixture = json.loads((Path(__file__).with_name("cases.json")).read_text(encoding="utf-8"))[0]
    messages = build_planner_messages(TechnicalPlanInput.model_validate(fixture["planner_input"]))
    client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
    spent, rows = 0.0, []
    for model in CANDIDATES:
        if model not in prices:
            continue
        input_price, output_price = prices[model]
        worst_case = estimate_cost(2_000, 700, input_price, output_price)
        if not can_spend(spent, worst_case):
            continue
        started = time.perf_counter()
        response = None
        try:
            response = client.chat.completions.create(model=model, messages=messages, response_format={"type": "json_object"}, max_tokens=700, temperature=0)
            content = response.choices[0].message.content or ""
            TechnicalPlan.model_validate(json.loads(content))
            usage = response.usage
            actual = estimate_cost(usage.prompt_tokens, usage.completion_tokens, input_price, output_price)
            spent += actual
            rows.append({"model": model, "valid": True, "latency_ms": round((time.perf_counter()-started)*1000), "estimated_cost": actual, "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
        except Exception as error:
            usage = getattr(response, "usage", None)
            actual = estimate_cost(usage.prompt_tokens, usage.completion_tokens, input_price, output_price) if usage else 0.0
            spent += actual
            preview = (response.choices[0].message.content or "")[:400] if response else ""
            rows.append({"model": model, "valid": False, "latency_ms": round((time.perf_counter()-started)*1000), "estimated_cost": actual, "error": type(error).__name__, "response_preview": preview})
    output = {"budget_usd": BUDGET_USD, "spent_usd": spent, "results": rows, "recommendation": recommend(rows)}
    Path(__file__).with_name("results.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    return rows

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run billable calls after verifying the configured cap.")
    args = parser.parse_args()
    if not args.live:
        raise SystemExit("Pass --live to make capped OpenRouter requests.")
    print(json.dumps({"results": run(), "report": "models/benchmark/results.json"}, indent=2))
