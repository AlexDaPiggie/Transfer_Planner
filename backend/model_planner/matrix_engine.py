import json
from typing import Any

def extract_courses_from_payload(payload: dict[str, Any]):
    courses = []
    series_rules = []
    notes = []

    # assist.org stores articulations as a JSON string
    raw_articulations = payload.get("articulations", [])
    if isinstance(raw_articulations, str):
        try:
            raw_articulations = json.loads(raw_articulations)
        except Exception:
            raw_articulations = []

    for art in raw_articulations:
        art_body = art.get("articulation", {})
        if not isinstance(art_body, dict):
            continue
        receiving = art_body.get("course", {}) or {}
        receiving_series = art_body.get("series", {}) or {}
        
        target_prefix = (receiving.get("prefix") or "").strip() if receiving else ""
        target_num = (receiving.get("courseNumber") or "").strip() if receiving else ""
        target_code = (
            receiving_series.get("name")
            or (f"{target_prefix} {target_num}".strip() if (target_prefix or target_num) else "Required Major Prep")
        )
        if receiving_series:
            series_courses = receiving_series.get("courses", [])
            series_name = receiving_series.get("name") or ", ".join(
                f"{item.get('prefix', '').strip()} {item.get('courseNumber', '').strip()}".strip()
                for item in series_courses
                if item.get("prefix") or item.get("courseNumber")
            )
            conjunction = (receiving_series.get("conjunction") or "And").upper()
            if series_name:
                series_rules.append(f"Complete the articulated series: {series_name} ({conjunction}).")

        for attribute_group in (
            art_body.get("attributes", []),
            art_body.get("courseAttributes", []),
            art_body.get("seriesAttributes", []),
            art_body.get("receivingAttributes", []),
            art.get("receivingAttributes", []),
        ):
            for attribute in attribute_group or []:
                content = attribute.get("content") if isinstance(attribute, dict) else None
                if content and content.strip():
                    notes.append(content.strip())

        sending_art = art_body.get("sendingArticulation") or {}
        no_articulation_reason = sending_art.get("noArticulationReason")
        if no_articulation_reason:
            notes.append(str(no_articulation_reason).strip())
        for attribute_group in (sending_art.get("attributes", []),):
            for attribute in attribute_group or []:
                content = attribute.get("content") if isinstance(attribute, dict) else None
                if content and content.strip():
                    notes.append(content.strip())

        for group in sending_art.get("items", []):
            group_courses = []
            for attribute in group.get("attributes", []) or []:
                content = attribute.get("content") if isinstance(attribute, dict) else None
                if content and content.strip():
                    notes.append(content.strip())
            group_items = group.get("items", [])
            group_conjunction = (group.get("courseConjunction") or "And").lower()
            for course_item in group_items:
                if course_item.get("type") == "Course":
                    prefix = (course_item.get("prefix") or "").strip()
                    num = (course_item.get("courseNumber") or "").strip()
                    title = (course_item.get("courseTitle") or "").strip()
                    units = float(course_item.get("minUnits", 0.0) or 0.0)

                    course = {
                        "cc_code": f"{prefix} {num}".strip(),
                        "cc_title": title,
                        "units": units,
                        "target_code": target_code,
                        "is_series": len(group_items) > 1 and group_conjunction == "and"
                    }
                    courses.append(course)
                    if course["cc_code"]:
                        group_courses.append(course["cc_code"])
                    for attribute in course_item.get("attributes", []) or []:
                        content = attribute.get("content") if isinstance(attribute, dict) else None
                        if content and content.strip():
                            notes.append(content.strip())
            if len(group_courses) > 1 and group_conjunction == "and":
                series_rules.append(f"Take the full course group: {' + '.join(group_courses)}.")

        if len(sending_art.get("items", [])) > 1:
            series_rules.append("This agreement has multiple course groups or options; check the Assist agreement for the exact combination.")

    return courses, list(dict.fromkeys(series_rules)), list(dict.fromkeys(notes))

def compute_overlap_matrix(agreements: list[dict[str, Any]]):
    course_map = {}
    all_series_rules = []
    all_notes = []
    total_targets = len(agreements)

    for ag in agreements:
        target_name = ag.get("target_school_name", "Target")
        payload = ag.get("payload", {})
        courses, series, notes = extract_courses_from_payload(payload)

        all_series_rules.extend(series)
        all_notes.extend(notes)

        for c in courses:
            code = c["cc_code"]
            if not code:
                continue

            if code not in course_map:
                course_map[code] = {
                    "code": code,
                    "title": c["cc_title"],
                    "units": c["units"],
                    "schools": {},
                    "is_series": c["is_series"]
                }
            course_map[code]["schools"][target_name] = c["target_code"]

    matrix_rows = []
    for code, data in course_map.items():
        matched_count = len(data["schools"])
        overlap_type = "Universal" if matched_count == total_targets else ("Partial" if matched_count > 1 else "Unique")

        matrix_rows.append({
            "code": code,
            "title": data["title"],
            "units": data["units"],
            "schools": data["schools"],
            "overlap_count": matched_count,
            "overlap_type": overlap_type,
            "is_series": data["is_series"]
        })

    matrix_rows.sort(key=lambda x: x["overlap_count"], reverse=True)
    return {
        "matrix": matrix_rows,
        "series_rules": all_series_rules,
        "raw_notes": all_notes,
        "total_targets": total_targets
    }
