import json
from pathlib import Path

def write_report() -> Path:
    source = Path(__file__).with_name("results.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    recommendation = data["recommendation"]
    lines = ["# Model benchmark report", "", f"Estimated spend: ${data['spent_usd']:.4f} of ${data['budget_usd']:.2f}", "", f"Primary: `{recommendation['primary']}`", f"Fallback: `{recommendation['fallback']}`", "", "This automatic ranking considers valid structured output first, then cost and latency. Review output quality on a larger curated fixture before treating it as a production-only decision.", "", "| Model | Valid JSON | Latency | Estimated cost |", "|---|---:|---:|---:|"]
    lines += [f"| {r['model']} | {r['valid']} | {r['latency_ms']} ms | ${r['estimated_cost']:.6f} |" for r in data["results"]]
    target = Path(__file__).with_name("report.md")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target

if __name__ == "__main__": print(write_report())
