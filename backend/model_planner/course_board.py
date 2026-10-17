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


def _choice_groups_from_agreement(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read Assist's explicit one-of instructions as switchable alternatives."""
    groups = []

    def cells_for_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cells = []
        for row in rows:
            for cell in row.get("cells", []) or []:
                cell_id = str(cell["id"]) if cell.get("id") is not None else None
                course = cell.get("course") or {}
                series_courses = (cell.get("series") or {}).get("courses") or []
                targets = series_courses or ([course] if course else [])
                codes = [
                    f"{target.get('prefix', '').strip()} {target.get('courseNumber', '').strip()}".strip()
                    for target in targets
                ]
                if cell_id or any(codes):
                    cells.append({"id": cell_id, "codes": [code for code in codes if code]})
        return cells

    def section_label(section: dict[str, Any], index: int) -> str:
        for key in ("label", "letter", "name", "title"):
            value = section.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return f"{chr(ord('A') + index)}" if index < 26 else f"{index + 1}"

    for asset_index, asset in enumerate(_json_list(payload.get("templateAssets", []))):
        if not isinstance(asset, dict) or asset.get("type") != "RequirementGroup":
            continue
        sections = [section for section in (asset.get("sections", []) or []) if isinstance(section, dict)]

        # Some Assist agreements put “complete 1 sequence from A, B, ...” on
        # the RequirementGroup itself. In that shape, each sibling section is
        # one alternative and every course row within that section is required.
        instruction = asset.get("instruction") or {}
        is_sequence_choice = False
        if isinstance(instruction, dict) and instruction.get("type") == "NFromConjunction":
            conjunction = str(instruction.get("conjunction", "")).casefold()
            selection = str(instruction.get("selectionType", "")).casefold()
            try:
                amount = float(instruction.get("amount", 0))
            except (TypeError, ValueError):
                amount = 0
            if conjunction == "or" and amount == 1 and selection in {"", "complete"}:
                options = []
                labels = []
                for section_index, section in enumerate(sections):
                    cells = cells_for_rows(section.get("rows", []) or [])
                    if cells:
                        options.append(cells)
                        labels.append(section_label(section, section_index))
                if len(options) > 1:
                    is_sequence_choice = True
                    groups.append({
                        "id": f"{asset_index}:sequence",
                        "kind": "sequence",
                        "options": options,
                        "option_labels": labels,
                    })

        # Nested section advisements belong to the parent sequence, so do not
        # turn them into additional top-level cards beside the sequence card.
        if is_sequence_choice:
            continue

        for section_index, section in enumerate(asset.get("sections", []) or []):
            if not isinstance(section, dict):
                continue
            for advisement_index, advisement in enumerate(section.get("advisements", []) or []):
                if not isinstance(advisement, dict) or advisement.get("type") != "NFollowing":
                    continue
                try:
                    amount = float(advisement.get("amount", 0))
                except (TypeError, ValueError):
                    continue
                unit_type = re.sub(r"[^a-z]", "", str(advisement.get("amountUnitType", "")).casefold())
                if amount != 1 or unit_type not in {"course", "courseorcombination"}:
                    continue
                options = []
                for row in section.get("rows", []) or []:
                    cells = cells_for_rows([row])
                    if cells:
                        options.append(cells)
                if options:
                    groups.append({
                        "id": f"{asset_index}:{section_index}:{advisement_index}",
                        "options": options,
                    })
    return groups


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


def _target_courses(articulation: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the receiving courses covered by a course or receiving series."""
    receiving = articulation.get("course") or {}
    series_courses = (articulation.get("series") or {}).get("courses") or []
    courses = series_courses or ([receiving] if receiving else [])
    targets = []
    for course in courses:
        course_id = course.get("courseIdentifierParentId")
        code = f"{course.get('prefix', '').strip()} {course.get('courseNumber', '').strip()}".strip()
        if code or course_id is not None:
            targets.append({"id": str(course_id) if course_id is not None else None, "code": code})
    if not targets:
        target_code, _ = _target_identity(articulation)
        targets.append({"id": None, "code": target_code})
    return targets


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
            options.append({
                "courses": courses,
                "conjunction": "or" if conjunction == "or" else "and",
                "is_series": conjunction == "and" and len(courses) > 1,
            })
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
            "target_courses": _target_courses(articulation),
            "target_is_series": bool(articulation.get("series")),
            "template_cell_id": str(entry.get("templateCellId")) if entry.get("templateCellId") is not None else None,
            "category": category,
            "options": options,
            "no_articulation_reason": no_articulation_reason,
            "honors_combination_allowed": honors_combination_allowed,
        }
    return requirements


def _choose_option(options: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Keep Assist's order when multiple valid articulated alternatives are provided."""
    return options[0] if options else None


def _course_stage_key(course: dict[str, Any]) -> tuple[str, str, bool]:
    """Group BIOL 6A and BIOL 6AH as the same displayed course stage."""
    parts = _series_course_parts(course["code"])
    if parts:
        return parts[0], parts[1], parts[2]
    return course["code"].upper(), "", False


def _build_university_plans(
    by_goal: dict[tuple[int, str], list[dict[str, Any]]],
    parsed: dict[tuple[int, int, str], dict[str, dict[str, Any]]],
    source_ids: list[int],
    main_source_id: int,
    source_position: dict[int, int],
    source_support: dict[int, int],
    choice_groups_by_source: dict[tuple[int, int, str], list[dict[str, Any]]],
    requested_year_id: int,
) -> list[dict[str, Any]]:
    """Build per-university plans, preferring a complete main-college route."""
    plans = []
    for (target_id, major), agreements in by_goal.items():
        agreement_by_source = {item["source_id"]: item for item in agreements}
        first = agreements[0]
        requirement_keys = sorted(set().union(*(
            parsed[(item["source_id"], item["target_id"], item["major"])].keys()
            for item in agreements
        )), key=str.casefold)

        # Assist's NFollowing advisement says to complete one displayed row (a
        # row can itself contain a course series), not every row in the section.
        reference_source = main_source_id if choice_groups_by_source.get((main_source_id, target_id, major)) else next((
            source_id for source_id in source_ids
            if choice_groups_by_source.get((source_id, target_id, major))
        ), None)
        reference_groups = choice_groups_by_source.get((reference_source, target_id, major), []) if reference_source is not None else []
        choice_cell_ids = {
            cell["id"]
            for source_id in source_ids
            for choice_group in choice_groups_by_source.get((source_id, target_id, major), [])
            for option_row in choice_group["options"]
            for cell in option_row
            if cell.get("id")
        }

        # Assist may represent the same receiving series as one row at one college
        # and several rows at another. Normalize course identifiers first, then
        # connect rows whose receiving-course sets overlap.
        id_by_code: dict[str, str] = {}
        for source_id in source_ids:
            for definition in parsed.get((source_id, target_id, major), {}).values():
                for course in definition.get("target_courses", []):
                    if course.get("id") and course.get("code"):
                        code = re.sub(r"\s+", " ", course["code"]).upper()
                        id_by_code.setdefault(code, course["id"])

        records = []
        for key in requirement_keys:
            per_source = {
                source_id: parsed.get((source_id, target_id, major), {}).get(key, {})
                for source_id in source_ids
            }
            definitions = [value for value in per_source.values() if value]
            if not definitions:
                continue
            if any(definition.get("template_cell_id") in choice_cell_ids for definition in definitions):
                continue
            tokens = set()
            target_codes = []
            target_pairs = []
            for definition in definitions:
                for course in definition.get("target_courses", []):
                    code = course.get("code", "").strip()
                    normalized = re.sub(r"\s+", " ", code).upper()
                    token = f"id:{course['id']}" if course.get("id") else f"id:{id_by_code[normalized]}" if normalized in id_by_code else f"code:{normalized}"
                    if normalized:
                        tokens.add(token)
                        target_pairs.append((code, token))
                        if code not in target_codes:
                            target_codes.append(code)
            if not tokens:
                tokens.add(f"label:{key.upper()}")
                target_codes.append(key)
                target_pairs.append((key, f"label:{key.upper()}"))
            records.append({
                "key": key,
                "per_source": per_source,
                "definitions": definitions,
                "tokens": tokens,
                "target_codes": target_codes,
                "target_pairs": list(dict.fromkeys(target_pairs)),
            })

        # Form connected requirement groups only when Assist rows share an actual
        # receiving course. This catches one-series-vs-split-row representations
        # without grouping unrelated courses that merely share a department.
        clusters: list[dict[str, Any]] = []
        for record in records:
            matching = [cluster for cluster in clusters if cluster["tokens"] & record["tokens"]]
            if not matching:
                clusters.append({"records": [record], "tokens": set(record["tokens"])})
                continue
            primary = matching[0]
            primary["records"].append(record)
            primary["tokens"].update(record["tokens"])
            for extra in matching[1:]:
                primary["records"].extend(extra["records"])
                primary["tokens"].update(extra["tokens"])
                clusters.remove(extra)

        label = f"{first['target_name']} — {major}"
        university = {
            "target_id": target_id,
            "university": first["target_name"],
            "major": major,
            "assist_url": None,
            "required": [],
            "recommended": [],
            "not_articulated": [],
        }

        for choice_group in reference_groups:
            options_by_source = {}
            for source_id in source_ids:
                definitions = parsed.get((source_id, target_id, major), {})
                keys_by_cell = {
                    definition.get("template_cell_id"): key
                    for key, definition in definitions.items()
                    if definition.get("template_cell_id")
                }
                keys_by_codes = {
                    frozenset(re.sub(r"\s+", " ", course.get("code", "")).upper() for course in definition.get("target_courses", []) if course.get("code")): definition
                    for definition in definitions.values()
                    if any(course.get("code") for course in definition.get("target_courses", []))
                }
                supported_rows = []
                for choice_index, row_cells in enumerate(choice_group["options"]):
                    row_defs = []
                    for cell in row_cells:
                        definition = definitions.get(keys_by_cell.get(cell.get("id"))) if cell.get("id") else None
                        if definition is None and cell.get("codes"):
                            code_set = frozenset(re.sub(r"\s+", " ", code).upper() for code in cell["codes"])
                            definition = keys_by_codes.get(code_set)
                        if definition is not None:
                            row_defs.append(definition)
                    if len(row_defs) == len(row_cells) and all(item.get("options") for item in row_defs):
                        supported_rows.append((choice_index, row_cells, row_defs))
                options_by_source[source_id] = supported_rows

            supported_sources = [source_id for source_id in source_ids if options_by_source[source_id]]
            if main_source_id in supported_sources:
                selected_source = main_source_id
            elif supported_sources:
                selected_source = max(supported_sources, key=lambda source_id: (len(options_by_source[source_id]), source_support[source_id], -source_position[source_id]))
            else:
                continue

            choices = []
            choice_definitions = []
            for choice_index, row_cells, row_defs in options_by_source[selected_source]:
                row_target_codes = []
                for definition in row_defs:
                    choice_definitions.append(definition)
                    codes = [course["code"] for course in definition.get("target_courses", []) if course.get("code")]
                    row_target_codes.extend(codes or [definition["target_code"]])
                row_combinations = [{"groups": [], "courses": [], "conjunction": "and", "is_series": False}]
                for definition in row_defs:
                    expanded = []
                    for combination in row_combinations:
                        for option in definition["options"]:
                            expanded.append({
                                "groups": combination["groups"] + [{"courses": option["courses"], "conjunction": option.get("conjunction", "and")}],
                                "courses": combination["courses"] + option["courses"],
                                "conjunction": "and",
                                "is_series": len(combination["courses"] + option["courses"]) > 1,
                            })
                    row_combinations = expanded[:32]
                row_combinations = [{
                    **combination,
                    "label": f"Option {index + 1} of {len(row_combinations)}",
                } for index, combination in enumerate(row_combinations)]
                choices.append({
                    "target_course": (
                        f"Sequence {choice_group['option_labels'][choice_index]}"
                        if choice_group.get("kind") == "sequence"
                        and choice_index < len(choice_group.get("option_labels", []))
                        else " + ".join(dict.fromkeys(row_target_codes))
                    ),
                    "options": row_combinations,
                })

            if not choices:
                continue
            category = "required" if any(item["category"] == "required" for item in choice_definitions) else "recommended"
            selected_agreement = agreement_by_source[selected_source]
            target_course = " OR ".join(choice["target_course"] for choice in choices)
            fallback_note = None
            if selected_source != main_source_id:
                fallback_note = (
                    f"{agreement_by_source.get(main_source_id, {}).get('source_name', 'Your main college')} "
                    "does not articulate an available choice in this requirement group. "
                    f"Choose one complete option at {selected_agreement['source_name']} instead."
                )
            university[category].append({
                "target_course": target_course,
                "target_title": target_course,
                "source_id": selected_source,
                "source_name": selected_agreement["source_name"],
                "is_main_college": selected_source == main_source_id,
                "choices": choices,
                # The first Assist course choice is the initial selection.
                "options": choices[0]["options"],
                "selection_note": (
                    "Complete 1 sequence from the following; choose one option."
                    if choice_group.get("kind") == "sequence"
                    else "Complete 1 course or combination from the following; choose one option."
                ),
                "fallback_note": fallback_note,
                "policy_note": "Regular and honors courses may be combined to complete this series." if any(item.get("honors_combination_allowed") for item in choice_definitions) else None,
                "assist_url": _build_assist_url(selected_agreement.get("year_id", requested_year_id), selected_source, target_id, selected_agreement["document_key"]),
            })

        for cluster in clusters:
            group_records = cluster["records"]
            group_tokens = cluster["tokens"]
            definitions = [definition for record in group_records for definition in record["definitions"]]
            category = "required" if any(item["category"] == "required" for item in definitions) else "recommended" if any(item["category"] == "recommended" for item in definitions) else "other"

            available_by_source: dict[int, list[dict[str, Any]]] = {}
            covered_by_source: dict[int, set[str]] = {}
            for source_id in source_ids:
                available = []
                covered = set()
                for record in group_records:
                    source_definition = record["per_source"].get(source_id, {})
                    if source_definition.get("options"):
                        available.append((record, source_definition))
                        covered.update(record["tokens"])
                available_by_source[source_id] = available
                covered_by_source[source_id] = covered

            complete_sources = [source_id for source_id in source_ids if group_tokens <= covered_by_source[source_id]]
            if category == "other" and complete_sources:
                continue
            if main_source_id in complete_sources:
                selected_source = main_source_id
            elif complete_sources:
                selected_source = max(complete_sources, key=lambda source_id: (source_support[source_id], -source_position[source_id]))
            else:
                main_missing = [code for record in group_records for code, token in record["target_pairs"] if token not in covered_by_source[main_source_id]]
                missing_label = ", ".join(dict.fromkeys(main_missing)) or ", ".join(dict.fromkeys(
                    code for record in group_records for code in record["target_codes"]
                ))
                no_options_anywhere = not any(available_by_source.values())
                assist_reason = next((definition.get("no_articulation_reason") for definition in definitions if definition.get("no_articulation_reason")), None)
                university["not_articulated"].append({
                    "target_course": missing_label,
                    "target_title": missing_label,
                    "reason": assist_reason if no_options_anywhere and assist_reason else f"No selected college offers a complete articulated route for this requirement group. The main college is missing: {missing_label}.",
                    "goal_label": label,
                })
                continue

            # Select the smallest set of this college's articulated rows that covers
            # the complete receiving group; a single series row wins over duplicates.
            remaining = set(group_tokens)
            cover = []
            candidates = list(available_by_source[selected_source])
            while remaining and candidates:
                best = max(candidates, key=lambda pair: (len(pair[0]["tokens"] & remaining), -len(pair[0]["tokens"]), pair[0]["key"]))
                contribution = best[0]["tokens"] & remaining
                if not contribution:
                    break
                cover.append(best)
                remaining.difference_update(contribution)
                candidates.remove(best)

            selected_agreement = agreement_by_source.get(selected_source)
            if not selected_agreement or remaining:
                continue

            # Each selected Assist row may itself have OR alternatives. Combine rows
            # with AND while preserving each row's own conjunction for display.
            combinations = [{"groups": [], "courses": [], "conjunction": "and", "is_series": False}]
            for _, source_definition in cover:
                expanded = []
                for combination in combinations:
                    for option in source_definition["options"]:
                        expanded.append({
                            "groups": combination["groups"] + [{"courses": option["courses"], "conjunction": option.get("conjunction", "and")}],
                            "courses": combination["courses"] + option["courses"],
                            "conjunction": "and",
                            "is_series": len(combination["courses"] + option["courses"]) > 1,
                        })
                        if len(expanded) >= 32:
                            break
                    if len(expanded) >= 32:
                        break
                combinations = expanded

            options = [{
                **option,
                "label": f"Option {index + 1} of {len(combinations)}" if len(combinations) > 1 else "Option 1 of 1",
            } for index, option in enumerate(combinations)]
            selected_codes = list(dict.fromkeys(code for record, _ in cover for code in record["target_codes"]))
            target_course = ", ".join(selected_codes) or group_records[0]["key"]
            fallback_note = None
            if selected_source != main_source_id:
                missing_at_main = [code for record in group_records for code, token in record["target_pairs"] if token not in covered_by_source[main_source_id]]
                if missing_at_main:
                    fallback_note = (
                        f"{agreement_by_source.get(main_source_id, {}).get('source_name', 'Your main college')} does not "
                        f"articulate {', '.join(dict.fromkeys(missing_at_main))} in this requirement group. "
                        f"Take the complete group at {selected_agreement['source_name']} instead."
                    )
            group = {
                "target_course": target_course,
                "target_title": target_course,
                "source_id": selected_source,
                "source_name": selected_agreement["source_name"],
                "is_main_college": selected_source == main_source_id,
                "options": options,
                "fallback_note": fallback_note,
                "policy_note": "Regular and honors courses may be combined to complete this series." if any(item.get("honors_combination_allowed") for item in definitions) else None,
                "assist_url": _build_assist_url(selected_agreement.get("year_id", requested_year_id), selected_source, target_id, selected_agreement["document_key"]),
            }
            if not university["assist_url"]:
                university["assist_url"] = group["assist_url"]
            university[category].append(group)

        for key in ("required", "recommended", "not_articulated"):
            university[key].sort(key=lambda group: group["target_course"].casefold())
        plans.append(university)
    return plans


def build_course_board(
    agreements: list[dict[str, Any]],
    requested_year_id: int,
    source_ids: list[int],
    main_source_id: int,
) -> dict[str, Any]:
    """Return Required/Recommended CC course cards and actionable articulation footnotes."""
    source_position = {source_id: index for index, source_id in enumerate(source_ids)}
    by_goal: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    parsed: dict[tuple[int, int, str], dict[str, dict[str, Any]]] = {}
    choice_groups_by_source: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
    for agreement in agreements:
        goal_key = (agreement["target_id"], agreement["major"])
        by_goal[goal_key].append(agreement)
        parsed[(agreement["source_id"], agreement["target_id"], agreement["major"])] = _requirements_from_agreement(agreement)
        choice_groups_by_source[(agreement["source_id"], agreement["target_id"], agreement["major"])] = _choice_groups_from_agreement(agreement["payload"])

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

    # The combined board is built from the same selected paths as the university panels.
    cards: dict[tuple[int, str, str], dict[str, Any]] = {}
    not_articulated_cards: dict[tuple[int, str], dict[str, Any]] = {}
    footnotes: list[str] = []
    university_plans = _build_university_plans(
        by_goal=by_goal,
        parsed=parsed,
        source_ids=source_ids,
        main_source_id=main_source_id,
        source_position=source_position,
        source_support=source_support,
        choice_groups_by_source=choice_groups_by_source,
        requested_year_id=requested_year_id,
    )

    # The combined board and model context come directly from the selected university paths.
    for university in university_plans:
        target_id = university["target_id"]
        major = university["major"]
        goal_key = f"{target_id}::{major}"
        goal_label = f"{university['university']} — {major}"
        dot_index = goal_indexes[goal_key]
        for category in ("required", "recommended"):
            for group in university[category]:
                for course in (group.get("options") or [{}])[0].get("courses", []):
                    family, stage, is_honors = _course_stage_key(course)
                    card_key = (group["source_id"], family, stage)
                    card = cards.setdefault(card_key, {
                        "source_id": group["source_id"],
                        "source_name": group["source_name"],
                        "variants": {},
                        "is_main_college": group["is_main_college"],
                        "goals": {},
                        "assist_urls": set(),
                        "category": category,
                        "fallback_notes": set(),
                        "policy_notes": set(),
                    })
                    card["variants"].setdefault("honors" if is_honors else "regular", course)
                    if category == "required":
                        card["category"] = "required"
                    previous_role = card["goals"].get(goal_key, {}).get("category")
                    card["goals"][goal_key] = {
                        "label": goal_label,
                        "dot_index": dot_index,
                        "category": "required" if previous_role == "required" else category,
                    }
                    card["assist_urls"].add(group["assist_url"])
                    if group.get("fallback_note"):
                        card["fallback_notes"].add(group["fallback_note"])
                    if group.get("policy_note"):
                        card["policy_notes"].add(group["policy_note"])
        for group in university["not_articulated"]:
            unavailable_key = (target_id, group["target_course"])
            unavailable = not_articulated_cards.setdefault(unavailable_key, {
                "course_code": group["target_course"],
                "course_name": group["target_title"],
                "reason": group["reason"],
                "goals": {},
            })
            unavailable["goals"][goal_key] = {"label": goal_label, "dot_index": dot_index}

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
        "universities": university_plans,
        "legend": goal_labels,
        "footnotes": list(dict.fromkeys(footnotes)),
    }
