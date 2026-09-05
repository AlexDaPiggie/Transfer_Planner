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
        receiving = art_body.get("course", {})
        
        target_prefix = receiving.get("prefix", "").strip() if receiving else ""
        target_num = receiving.get("courseNumber", "").strip() if receiving else ""
        target_code = f"{target_prefix} {target_num}".strip() if (target_prefix or target_num) else "Required Major Prep"

        sending_art = art_body.get("sendingArticulation", {})
        for group in sending_art.get("items", []):
            for course_item in group.get("items", []):
                if course_item.get("type") == "Course":
                    prefix = course_item.get("prefix", "").strip()
                    num = course_item.get("courseNumber", "").strip()
                    title = course_item.get("courseTitle", "").strip()
                    units = float(course_item.get("minUnits", 0.0) or 0.0)

                    courses.append({
                        "cc_code": f"{prefix} {num}".strip(),
                        "cc_title": title,
                        "units": units,
                        "target_code": target_code,
                        "is_series": len(group.get("items", [])) > 1
                    })

    return courses, series_rules, notes

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