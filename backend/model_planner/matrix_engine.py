from typing import Any
def extract_course_from_payload(payload: dict[str, Any]):
    """This is to extract the courses, contraints for groups of coureses (e.g. math1a+1b+c) and footnotes from the page"""
    courses = [] # store courses
    series_rules = [] #store constraints for groups of sbjs
    notes = []

    for sec in payload.get("templateAssets", []) or []:
        sending = sec.get("sendingCourse")
        receiving = sec.get("receivingCourse")
        is_series = sec.get("isSeries", False)

        if sending:
            prefix = sending.get("prefix", "").strip()
            num = sending.get("prefix", "").strip()
            title = sending.get("courseTitle", "").strip()
            units = float(sending.get("units", 0.0) or 0.0)

            target_prefix = receiving.get("prefix", "").strip() if receiving else ""
            target_num = receiving.get("courseNumber", "").strip() if receiving else ""
            target_code = f"{target_prefix} {target_num}".strip() if (target_prefix or target_num) else "Required Course for Transfering"

            courses.append({
                "cc_code": f"{prefix} {num}".strip(),
                "cc_title": title,
                "units": units,
                "target_code": target_code,
                "is_series": is_series,
            })

    for note in payload.get("notes", []) or []:
        if isinstance(note, str) and note.strip():
            notes.append(note.strip())

    return courses, series_rules, notes

def compute_overlap_matrix(aggrements: list[dict[str, Any]]):
    """This is to calculate cross-uni course overlap matrix and sort by overlap count"""
    course_map: dict[str, dict[str, Any]] = {}
    all_series_rules = []
    all_notes = []
    total_targets = len(aggrements)

    for ag in aggrements:
        target_name = ag.get("target_school_name", "Target")
        payload = ag.get("payload", {})
        courses, series, notes = extract_course_from_payload(payload)

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
                    "unties": c["units"],
                    "schools": {},
                    "is_series": c["is_series"]
                }

            course_map[code]["schools"][target_name] = c["target_code"]

    matrix_rows = []

    for code, data in course_map.items():
        matched_count = len(data["schools"])

        if matched_count == total_targets:
            overlap_type = "Universal"
        elif matched_count > 1:
            overlap_type = "Partial"
        else:
            overlap_type = "Unique"

        matrix_rows.append({
            "code": code,
            "title": data["title"],
            "units": data["units"],
            "schools": data["schools"],
            "overlap_count": data["overlap_count"],
            "overlap_type": overlap_type,
            "is_series": data["is_series"],
        })

    matrix_rows.sort(key = lambda x: x["overlap_count"], reverse = True)
    return {
        "matrix": matrix_rows,
        "series_rule": all_series_rules,
        "raw_notes": all_notes,
        "total_targets": total_targets
    }