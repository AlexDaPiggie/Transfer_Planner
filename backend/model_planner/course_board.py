"""Build a student-facing course board from saved Assist major agreements."""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlencode


def _build_assist_url(year_id: int, source_id: int, target_id: int, document_key: str) -> str:
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


def _json_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return value if isinstance(value, list) else []


def _text_from_template_assets(payload: dict[str, Any]) -> str:
    assets = _json_list(payload.get("templateAssets", []))
    raw_text = " ".join(str(asset.get("content", "")) for asset in assets if isinstance(asset, dict))
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw_text))
    return re.sub(r"\s+", " ", text).strip()


def _category_sections(payload: dict[str, Any]) -> tuple[str, str]:
    """Return the Assist text that describes required and strongly recommended courses."""
    text = _text_from_template_assets(payload)
    recommended_match = re.search(r"\bstrongly\s+recommended\s+courses?\b", text, re.IGNORECASE)
    recommended_start = recommended_match.start() if recommended_match else len(text)
    required_matches = list(re.finditer(r"\brequired(?:\s+[\w/-]+){0,5}\s+courses?\b", text[:recommended_start], re.IGNORECASE))
    required_start = required_matches[-1].start() if required_matches else -1
    required_text = text[required_start:recommended_start] if required_start >= 0 else ""
    recommended_text = text[recommended_start:] if recommended_match else ""
    return required_text, recommended_text


def _course_category(target_code: str, required_text: str, recommended_text: str) -> str:
    """Classify a receiving course from Assist's own Required/Recommended headings."""
    target_code = target_code.strip()
    normalized_code = re.escape(target_code).replace(r"\ ", r"\s+")
    if not target_code:
        return "other"

    def contains_course(section: str) -> bool:
        direct_pattern = re.compile(rf"(?<![\w]){normalized_code}(?![\w])", re.IGNORECASE)
        if direct_pattern.search(section):
            return True
        # Assist frequently shortens a list to "MATH 51; 52; 53; 54".
        pieces = target_code.rsplit(" ", 1)
        if len(pieces) == 2:
            prefix, number = pieces
            shorthand_pattern = re.compile(
                rf"(?<![\w]){re.escape(prefix)}\s+[\w-]+(?:\s*[;,/]\s*[\w-]+){{0,8}}\s*[;,/]\s*{re.escape(number)}(?![\w])",
                re.IGNORECASE,
            )
            if shorthand_pattern.search(section):
                return True
        # A receiving series can be formatted differently (for example, "BIOLOGY 1A/1AL").
        first_course = re.split(r"\s*[,;+]\s*", target_code)[0]
        if first_course != target_code:
            first_escaped = re.escape(first_course).replace(r"\ ", r"\s+")
            first_pattern = re.compile(rf"(?<![\w]){first_escaped}(?![\w])", re.IGNORECASE)
            return bool(first_pattern.search(section))
        return False

    if contains_course(required_text):
        return "required"
    if contains_course(recommended_text):
        return "recommended"
    return "other"


def _target_identity(articulation: dict[str, Any]) -> tuple[str, str]:
    receiving = articulation.get("course") or {}
    receiving_series = articulation.get("series") or {}
    series_courses = receiving_series.get("courses") or []
    series_codes = [
        f"{item.get('prefix', '').strip()} {item.get('courseNumber', '').strip()}".strip()
        for item in series_courses
        if item.get("prefix") or item.get("courseNumber")
    ]
    target_code = receiving_series.get("name") or f"{receiving.get('prefix', '').strip()} {receiving.get('courseNumber', '').strip()}".strip()
    target_title = receiving_series.get("name") or receiving.get("courseTitle") or target_code
    if not target_code and series_codes:
        target_code = " + ".join(series_codes)
        target_title = target_code
    return target_code or "Required major preparation", target_title or "Required major preparation"


def _sending_options(articulation: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    sending = articulation.get("sendingArticulation") or {}
    options = []
    for group in sending.get("items", []) or []:
        courses = []
        for item in group.get("items", []) or []:
            if item.get("type") != "Course":
                continue
            code = f"{item.get('prefix', '').strip()} {item.get('courseNumber', '').strip()}".strip()
            if not code:
                continue
            courses.append({
                "code": code,
                "title": (item.get("courseTitle") or "").strip(),
                "units": float(item.get("minUnits", 0.0) or 0.0),
            })
        if courses:
            conjunction = (group.get("courseConjunction") or "And").lower()
            options.append({"courses": courses, "is_series": conjunction == "and" and len(courses) > 1})
    return options, sending.get("noArticulationReason")


def _series_course_parts(code: str) -> tuple[str, str, bool] | None:
    """Split ``BIOL 6AH`` into (``BIOL 6``, ``A``, True)."""
    match = re.match(r"^(.*?\s+\d+)([A-Z]+?)(H)?$", code.strip(), re.IGNORECASE)
    if not match:
        return None
    prefix, sequence_part, honors = match.groups()
    return prefix.upper(), sequence_part.upper(), bool(honors)

def _requirements_from_agreement(agreement: dict[str, Any]) -> dict[str, dict[str, Any]]:
    payload = agreement["payload"]
    required_text, recommended_text = _category_sections(payload)
    agreement_text = _text_from_template_assets(payload)
    agreement_wide_required = bool(re.search(
        r"major\s+courses?.{0,100}required\s+for\s+admissions|"
        r"lower-division\s+courses?\s+required\s+in\s+major|"
        r"lower-division\s+course\s+requirements?\s+specific\s+to\s+the\s+major|"
        r"\bmajor\s+requirements\b",
        agreement_text,
        re.IGNORECASE,
    ))
    honors_combination_allowed = bool(re.search(
        r"regular\s+and\s+honou?rs\s+courses?\s+may\s+be\s+combined\s+to\s+complete\s+(?:this|the)\s+series",
        agreement_text,
        re.IGNORECASE,
    ))
    requirements: dict[str, dict[str, Any]] = {}
    for entry in _json_list(payload.get("articulations", [])):
        articulation = entry.get("articulation") or {}
        if not isinstance(articulation, dict):
            continue
        target_code, target_title = _target_identity(articulation)
        options, no_articulation_reason = _sending_options(articulation)
        category = _course_category(target_code, required_text, recommended_text)
        if category == "other" and agreement_wide_required:
            category = "required"
        requirements[target_code] = {
            "target_code": target_code,
            "target_title": target_title,
            "category": category,
            "options": options,
            "no_articulation_reason": no_articulation_reason,
            "honors_combination_allowed": honors_combination_allowed,
        }
    return requirements


def _choose_option(options: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Keep Assist's order when multiple valid articulated alternatives are provided."""
    return options[0] if options else None


def _option_series_families(options: list[dict[str, Any]]) -> set[str]:
    """Return source-course series families, such as ``BIOL 6``."""
    return {
        parts[0]
        for option in options
        for course in option["courses"]
        if (parts := _series_course_parts(course["code"]))
    }


def _course_stage_key(course: dict[str, Any]) -> tuple[str, str, bool]:
    """Group BIOL 6A and BIOL 6AH as the same displayed course stage."""
    parts = _series_course_parts(course["code"])
    if parts:
        return parts[0], parts[1], parts[2]
    return course["code"].upper(), "", False


def build_course_board(
    agreements: list[dict[str, Any]],
    requested_year_id: int,
    source_ids: list[int],
    main_source_id: int,
) -> dict[str, Any]:
    """Return Required/Recommended CC course cards and actionable articulation footnotes."""
    source_position = {source_id: index for index, source_id in enumerate(source_ids)}
    source_names = {item["source_id"]: item["source_name"] for item in agreements}
    by_goal: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    parsed: dict[tuple[int, int, str], dict[str, dict[str, Any]]] = {}
    for agreement in agreements:
        goal_key = (agreement["target_id"], agreement["major"])
        by_goal[goal_key].append(agreement)
        parsed[(agreement["source_id"], agreement["target_id"], agreement["major"])] = _requirements_from_agreement(agreement)

    goal_labels = []
    for target_id, major in by_goal:
        item = by_goal[(target_id, major)][0]
        goal_labels.append({"key": f"{target_id}::{major}", "label": f"{item['target_name']} — {major}"})
    goal_indexes = {item["key"]: index for index, item in enumerate(goal_labels)}

    # Count how many target requirements each selected college can fulfill. This ranks backup colleges.
    source_support = defaultdict(int)
    for goal_key, goal_agreements in by_goal.items():
        requirement_keys = set().union(*(
            parsed[(item["source_id"], item["target_id"], item["major"])].keys()
            for item in goal_agreements
        ))
        for source_id in source_ids:
            requirement_map = parsed.get((source_id, goal_key[0], goal_key[1]), {})
            source_support[source_id] += sum(bool(_choose_option(requirement_map.get(key, {}).get("options", []))) for key in requirement_keys)

    # Course-stage cards deliberately keep ``BIOL 6A or BIOL 6AH`` together,
    # without turning an entire multi-course series into one oversized card.
    cards: dict[tuple[int, str, str], dict[str, Any]] = {}
    not_articulated_cards: dict[tuple[int, str], dict[str, Any]] = {}
    footnotes: list[str] = []
    for (target_id, major), goal_agreements in by_goal.items():
        first_agreement = goal_agreements[0]
        goal_key = f"{target_id}::{major}"
        requirement_keys = set().union(*(
            parsed[(item["source_id"], item["target_id"], item["major"])].keys()
            for item in goal_agreements
        ))
        requirement_data: dict[str, dict[str, Any]] = {}
        series_groups: dict[str, list[str]] = defaultdict(list)
        for requirement_key in requirement_keys:
            per_source = {
                item["source_id"]: parsed[(item["source_id"], item["target_id"], item["major"])].get(requirement_key, {})
                for item in goal_agreements
            }
            definition = next((item for item in per_source.values() if item), {})
            category = definition.get("category", "other")
            has_articulated_option = any(
                _choose_option(item.get("options", []))
                for item in per_source.values()
                if item
            )
            if not has_articulated_option:
                unavailable_key = (target_id, definition.get("target_code", requirement_key))
                unavailable = not_articulated_cards.setdefault(unavailable_key, {
                    "course_code": definition.get("target_code") or "Required major preparation",
                    "course_name": definition.get("target_title") or definition.get("target_code") or "Required major preparation",
                    "reason": definition.get("no_articulation_reason") or "No selected community college has an articulated course for this university requirement.",
                    "goals": {},
                })
                unavailable["goals"][goal_key] = {
                    "label": f"{first_agreement['target_name']} — {major}",
                    "dot_index": goal_indexes[goal_key],
                }
            if category == "other":
                continue
            families = set().union(*(
                _option_series_families(item.get("options", []))
                for item in per_source.values()
                if item
            ))
            series_family = next(iter(families)) if len(families) == 1 else None
            requirement_data[requirement_key] = {
                "per_source": per_source,
                "definition": definition,
                "category": category,
                "series_family": series_family,
            }
            if series_family:
                series_groups[series_family].append(requirement_key)

        selected_by_requirement: dict[str, tuple[int, list[dict[str, Any]]]] = {}
        fallback_notes: dict[str, str] = {}
        for series_family, keys in series_groups.items():
            is_series = len(keys) > 1 or any(
                any(option["is_series"] for option in requirement_data[key]["per_source"].get(source_id, {}).get("options", []))
                for key in keys
                for source_id in source_ids
            )
            if not is_series:
                continue
            complete_candidates = [
                source_id for source_id in source_ids
                if all(requirement_data[key]["per_source"].get(source_id, {}).get("options", []) for key in keys)
            ]
            if not complete_candidates:
                continue
            chosen_source_id = main_source_id if main_source_id in complete_candidates else max(
                complete_candidates,
                key=lambda source_id: (source_support[source_id], -source_position[source_id]),
            )
            for key in keys:
                selected_by_requirement[key] = (
                    chosen_source_id,
                    requirement_data[key]["per_source"][chosen_source_id]["options"],
                )
            if chosen_source_id != main_source_id:
                missing_courses = [
                    requirement_data[key]["definition"].get("target_code", "a required course")
                    for key in keys
                    if not requirement_data[key]["per_source"].get(main_source_id, {}).get("options", [])
                ]
                if missing_courses:
                    note = (
                        f"{source_names.get(main_source_id, 'Your main college')} does not articulate "
                        f"{' and '.join(missing_courses)} in the {series_family} series required by "
                        f"{first_agreement['target_name']} — {major}. Take the full {series_family} series at "
                        f"{source_names.get(chosen_source_id, f'Community college #{chosen_source_id}')} instead."
                    )
                    for key in keys:
                        fallback_notes[key] = note

        for requirement_key, item_data in requirement_data.items():
            per_source = item_data["per_source"]
            definition = item_data["definition"]
            category = item_data["category"]

            candidates = []
            for source_id in source_ids:
                options = per_source.get(source_id, {}).get("options", [])
                if options:
                    candidates.append((source_id, options))
            selected = selected_by_requirement.get(requirement_key)
            if not selected:
                main_candidate = next((candidate for candidate in candidates if candidate[0] == main_source_id), None)
                selected = main_candidate or (max(candidates, key=lambda candidate: (source_support[candidate[0]], -source_position[candidate[0]])) if candidates else None)

            if not selected:
                continue

            source_id, selected_options = selected
            agreement = next(item for item in goal_agreements if item["source_id"] == source_id)
            for option in selected_options:
                for course in option["courses"]:
                    family, stage, is_honors = _course_stage_key(course)
                    card_key = (source_id, family, stage)
                    card = cards.setdefault(card_key, {
                        "source_id": source_id,
                        "source_name": source_names.get(source_id, f"Community college #{source_id}"),
                        "variants": {},
                        "is_main_college": source_id == main_source_id,
                        "goals": {},
                        "assist_urls": set(),
                        "category": category,
                        "fallback_notes": set(),
                        "policy_notes": set(),
                    })
                    variant_key = "honors" if is_honors else "regular"
                    card["variants"].setdefault(variant_key, course)
                    if category == "required":
                        card["category"] = "required"
                    card["goals"][goal_key] = {"label": f"{agreement['target_name']} — {major}", "dot_index": goal_indexes[goal_key]}
                    card["assist_urls"].add(_build_assist_url(agreement.get("year_id", requested_year_id), source_id, target_id, agreement["document_key"]))
                    if requirement_key in fallback_notes:
                        card["fallback_notes"].add(fallback_notes[requirement_key])
                    if definition.get("honors_combination_allowed"):
                        card["policy_notes"].add("Regular and honors courses may be combined to complete this series.")

    required_cards, recommended_cards = [], []
    for card in cards.values():
        variants = [card["variants"][key] for key in ("regular", "honors") if key in card["variants"]]
        card["course_code"] = " or ".join(course["code"] for course in variants)
        card["course_name"] = variants[0].get("title") or variants[0]["code"]
        card["units"] = max((course["units"] for course in variants), default=0)
        card["fallback_notes"] = sorted(card["fallback_notes"])
        card["policy_notes"] = sorted(card["policy_notes"])
        card["goals"] = list(card["goals"].values())
        card["supports_count"] = len(card["goals"])
        card["assist_urls"] = sorted(card["assist_urls"])
        destination = required_cards if card["category"] == "required" else recommended_cards
        destination.append(card)
    sort_key = lambda item: (-item["supports_count"], not item["is_main_college"], item["course_code"])
    required_cards.sort(key=sort_key)
    recommended_cards.sort(key=sort_key)
    not_articulated = list(not_articulated_cards.values())
    for card in not_articulated:
        card["goals"] = list(card["goals"].values())
        card["supports_count"] = len(card["goals"])
    not_articulated.sort(key=lambda item: (-item["supports_count"], item["course_code"]))
    return {
        "required": required_cards,
        "recommended": recommended_cards,
        "not_articulated": not_articulated,
        "legend": goal_labels,
        "footnotes": list(dict.fromkeys(footnotes)),
    }
