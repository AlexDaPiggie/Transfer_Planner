from .schemas import ChatInput, TechnicalPlanInput

PLANNER_SYSTEM_PROMPT = """You are a California transfer-articulation planner. Use only the verified matrix, series rules, notes, and official URLs provided. Do not invent requirements, equivalencies, grades, deadlines, or sources. Return JSON only, with exactly these fields: {"summary":"plain text","course_priorities":["course code: reason"],"warnings":["warning"],"source_urls":["https://official.example"]}. Every source_urls value must be copied exactly from the supplied official_url values. All four fields are required, and every list must contain at least one item when source data exists. Keep the summary concise and return at most 30 prioritized courses."""
EXPLAINER_SYSTEM_PROMPT = """You are a careful student-facing transfer guide. Explain only the supplied verified plan. Do not invent requirements or links. Clearly label uncertainty and direct the student to the official Assist.org source URL when discussing a requirement."""

def build_planner_messages(data: TechnicalPlanInput) -> list[dict[str, str]]:
    return [{"role": "system", "content": PLANNER_SYSTEM_PROMPT}, {"role": "user", "content": data.model_dump_json()}]

def build_summary_messages(plan_context: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": EXPLAINER_SYSTEM_PROMPT}, {"role": "user", "content": f"Create a concise Markdown student summary from this verified plan:\n{plan_context}"}]

def build_chat_messages(data: ChatInput) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": f"{EXPLAINER_SYSTEM_PROMPT}\n\nVerified plan:\n{data.plan_context}"}]
    messages.extend(item.model_dump() for item in data.history[-6:])
    messages.append({"role": "user", "content": data.message})
    return messages
