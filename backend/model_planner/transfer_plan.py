"""Deterministic transfer-plan calculations built only from saved agreement data."""
from urllib.parse import urlencode


def build_assist_url(year_id: int, source_id: int, target_id: int, document_key: str) -> str:
    """Build the public Assist agreement URL from the identity saved with an agreement."""
    query = urlencode({
        "year": year_id,
        "institution": source_id,
        "agreement": target_id,
        "agreementType": "to",
        "viewAgreementsOptions": "true",
        "view": "agreement",
        "viewBy": "major",
        "viewSendingAgreements": "false",
        "viewByKey": document_key,
    })
    return f"https://assist.org/transfer/results?{query}"


def build_transfer_plan(agreements: list[dict], year_id: int, main_source_id: int | None = None) -> dict:
    """Return prioritized course actions and transparent target coverage without an LLM."""
    target_ids = {f"{item['target_id']}::{item['major']}" for item in agreements}
    goal_names = {
        f"{item['target_id']}::{item['major']}": f"{item['target_name']} — {item['major']}"
        for item in agreements
    }
    actions: dict[tuple[int, str], dict] = {}
    target_details = []
    for agreement in agreements:
        target_key = f"{agreement['target_id']}::{agreement['major']}"
        target_details.append({
            "target_key": target_key,
            "university": agreement["target_name"],
            "major": agreement["major"],
            "assist_url": build_assist_url(year_id, agreement["source_id"], agreement["target_id"], agreement["document_key"]),
        })
        for course in agreement["courses"]:
            action_key = (agreement["source_id"], course["code"])
            action = actions.setdefault(action_key, {
                "source_id": agreement["source_id"],
                "source_name": agreement["source_name"],
                "course_code": course["code"],
                "course_name": course["title"],
                "units": course.get("units", 0),
                "supports": set(),
                "assist_urls": set(),
            })
            action["supports"].add(target_key)
            action["assist_urls"].add(build_assist_url(year_id, agreement["source_id"], agreement["target_id"], agreement["document_key"]))

    recommended = []
    for action in actions.values():
        supports = sorted(action.pop("supports"))
        urls = sorted(action.pop("assist_urls"))
        action["supports"] = supports
        action["supports_count"] = len(supports)
        action["supported_goals"] = [goal_names[key] for key in supports]
        action["assist_urls"] = urls
        action["is_main_college"] = action["source_id"] == main_source_id
        action["category"] = "all_targets" if len(supports) == len(target_ids) else ("shared" if len(supports) > 1 else "target_specific")
        recommended.append(action)
    recommended.sort(key=lambda row: (-row["supports_count"], not row["is_main_college"], row["units"], row["course_code"], row["source_name"]))
    return {
        "coverage": {"selected_targets": len(target_ids), "course_actions": len(recommended)},
        "recommended_courses": recommended,
        "targets": target_details,
        "warnings": ["Course coverage is based on saved Assist agreements. Verify all current policies and full course sequences using the linked agreement."],
    }
