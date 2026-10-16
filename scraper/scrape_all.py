import time 
from scraper.assist_api import AssistAPI
from scraper.sync_db import init_db, save_agreement, get_db_connection, save_institutions
import os
from dotenv import load_dotenv
import json
import sys
import subprocess
from backend.model_planner.matrix_engine import extract_courses_from_payload

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

def remove_dead_route(
    year_id: int,
    source_id: int,
    target_id: int,
):
    """
    This function is to delete the old agreements from the local database if a CC and UNI stop partnering

    Input: ids of year, source, target
    Ouptut: NA
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM agreements
        WHERE year_id=%s AND source_school_id=%s AND target_school_id=%s
""", (year_id, source_id, target_id))
    conn.commit()
    conn.close()

def remove_dead_majors(
    year_id: int,
    source_id: int,
    target_id: int,
    official_majors: list,
):
    """
    This function is to remove the majors that are no longer supported by the university
    Input: ids of year, source, target, majors
    Output: NA
    """
    if not official_majors:
        return 

    conn = get_db_connection()
    cur = conn.cursor()

    #Create a string of "?" as placeholder for the majors
    placeholders = ",".join(["%s"] * len(official_majors))
    query = f"""
        DELETE FROM agreements
        WHERE year_id=%s AND source_school_id=%s AND target_school_id=%s
        AND major_name NOT IN ({placeholders})
"""
    #Combine ids and major names into a list
    params = [year_id, source_id, target_id] + official_majors
    cur.execute(query, params)
    conn.commit()
    conn.close()

def is_up_to_date(
    year_id: int,
    source_id: int,
    target_id: int,
    major_name: str,
    api_key: str,
):
    """This function is to traverse throughout the database and compare the unique document key, seeing if it's different(sign of update)"""

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT document_key FROM agreements
        WHERE year_id=%s AND source_school_id=%s AND target_school_id=%s AND major_name=%s
""", (year_id, source_id, target_id, major_name))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False #Major not in the database

    db_key = row[0]
    return db_key == api_key #true if the date mathches, false if there's new update

def get_saved_agreement(year_id: int, source_id: int, target_id: int, major_name: str):
    """Return a saved detail payload, if one exists for this exact Assist year."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT raw_json FROM agreements
        WHERE year_id=%s AND source_school_id=%s AND target_school_id=%s AND major_name=%s
    """, (year_id, source_id, target_id, major_name))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])

def save_if_changed(api: AssistAPI, year_id: int, source_id: int, target_id: int, report: dict):
    """Fetch and save one report only when Assist's document key has changed."""
    major = report["label"]
    key = report["key"]
    changed = not is_up_to_date(year_id, source_id, target_id, major, key)
    if changed:
        detail = fetch_with_retry(api, key)
        save_agreement(year_id, source_id, target_id, major, key, detail)
    else:
        detail = get_saved_agreement(year_id, source_id, target_id, major)
    return detail or {}, changed

def fetch_with_retry(api: AssistAPI, key: str, max_retries: int = 5):
    """To fetch agreement details again when facing 429 err"""
    for attempt in range(max_retries):
        try:
            return api.get_agreement_details(key)
        except Exception as e:
            if "429" in str(e):
                wait_time = 10 * (attempt + 1)  # 10s, 20s, 30s...
                print(f"    [Rate Limited 429] Resetting session and cooling down for {wait_time}s (Attempt {attempt+1}/{max_retries})...")
                api.refresh_session()
                time.sleep(wait_time)
            else:
                raise e
    raise Exception(f"Failed after {max_retries} retries for key {key}")


def articulated_course_count(detail: dict) -> int:
    """Count usable sending-college courses in an Assist agreement detail payload."""
    courses, _, _ = extract_courses_from_payload(detail)
    return len({course["cc_code"] for course in courses if course.get("cc_code")})

def scrape_all_agreements(
    year_id: int = 77,
    delay_seconds: float = 0.8,
    source_school_id: int = None,
    source_school_ids: list[int] = None,
):

    init_db()
    api = AssistAPI()

    institutions = api.get_institutions()
    save_institutions(institutions)
    ccc_schools = [i for i in institutions if i.get("isCommunityCollege", False)]
    uni_schools = [i for i in institutions if not i.get("isCommunityCollege", False)]

    if source_school_id is not None and source_school_ids is not None:
        raise ValueError("Specify source_school_id or source_school_ids, not both")

    task_index = int(os.getenv("CLOUD_RUN_TASK_INDEX", "0"))
    task_count = int(os.getenv("CLOUD_RUN_TASK_COUNT", "1"))
    if task_count < 1 or task_index < 0 or task_index >= task_count:
        raise ValueError(f"Invalid Cloud Run task position: {task_index}/{task_count}")

    selected_ids = source_school_ids
    if source_school_id is not None:
        selected_ids = [source_school_id]

    if selected_ids is not None:
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("Community college IDs must not contain duplicates")
        schools_by_id = {school["id"]: school for school in ccc_schools}
        missing_ids = [school_id for school_id in selected_ids if school_id not in schools_by_id]
        if missing_ids:
            raise ValueError(f"No California Community College found with ID(s): {missing_ids}")
        selected_ccs = [schools_by_id[school_id] for school_id in selected_ids]
        my_ccs = [school for index, school in enumerate(selected_ccs) if index % task_count == task_index]
    else:
        my_ccs = [ccc for idx, ccc in enumerate(ccc_schools) if idx % task_count == task_index]

    total_ccs = len(ccc_schools)
    total_saved = 0
    start_time = time.time()
    assigned_ccs = len(my_ccs)
    completed_ccs = 0

    print(
        f"RUN START | worker={task_index + 1}/{task_count} | year={year_id} | "
        f"scope={'selected' if selected_ids is not None else 'all'} | "
        f"requested_ccs={selected_ids if selected_ids is not None else total_ccs} | "
        f"total_ccs={total_ccs} | assigned_ccs={assigned_ccs} | universities={len(uni_schools)}"
    )

    for worker_cc_idx, ccc in enumerate(my_ccs, start=1):
        ccc_name = ccc["names"][0]["name"]

        #Update the starting ids of cc from the current progress
        real_idx = ccc_schools.index(ccc) + 1
        pct = (real_idx / total_ccs) * 100
        print(
            f"CC START | worker={task_index + 1}/{task_count} | "
            f"global_cc={real_idx}/{total_ccs} | worker_cc={worker_cc_idx}/{assigned_ccs} | "
            f"name={ccc_name}"
        )

        cc_majors_saved = 0
        cc_courses_count = 0

        #Update the starting ids  of the universities from the current progresss

        for uni in uni_schools:
            uni_name = uni["names"][0]["name"]
            try:
                print(
                    f"PAIR CHECK | worker={task_index + 1}/{task_count} | "
                    f"global_cc={real_idx}/{total_ccs} | worker_cc={worker_cc_idx}/{assigned_ccs} | "
                    f"cc={ccc_name} | university={uni_name}"
                )
                reports = api.get_agreements_list(year_id, ccc["id"], uni["id"])
                fallback_year_id = 76 if year_id == 77 else None
                report_by_major = {report["label"]: report for report in reports}
                zero_course_majors = set()
                saved_for_this_uni = 0

                if reports:
                    remove_dead_majors(year_id, ccc["id"], uni["id"], list(report_by_major))
                elif year_id == 77:
                    # An empty current-year report list means old year-77 rows must not mask year-76 fallback.
                    remove_dead_route(year_id, ccc["id"], uni["id"])
                    print(
                        f"PAIR EMPTY | worker={task_index + 1}/{task_count} | cc={ccc_name} | "
                        f"university={uni_name} | action=cleared_stale_year_{year_id}_rows_checking_year_76"
                    )

                print(
                    f"PAIR PLAN | worker={task_index + 1}/{task_count} | "
                    f"global_cc={real_idx}/{total_ccs} | cc={ccc_name} | university={uni_name} | "
                    f"year_{year_id}_majors={len(reports)}"
                )

                # Save current-year reports, and flag explicit no-course agreements for fallback.
                for report_idx, report in enumerate(reports, start=1):
                    detail, changed = save_if_changed(api, year_id, ccc["id"], uni["id"], report)
                    course_count = articulated_course_count(detail)
                    if not course_count:
                        zero_course_majors.add(report["label"])
                    if changed:
                        total_saved += 1
                        cc_majors_saved += 1
                        cc_courses_count += course_count
                        saved_for_this_uni += 1
                        print(
                            f"AGREEMENT SAVED | year={year_id} | cc={ccc_name} | university={uni_name} | "
                            f"major={report['label']} | courses={course_count} | "
                            f"progress={report_idx}/{len(reports)}"
                        )
                        time.sleep(delay_seconds)

                fallback_reports = []
                if fallback_year_id is not None:
                    current_major_names = set(report_by_major)
                    fallback_reports = api.get_agreements_list(fallback_year_id, ccc["id"], uni["id"])
                    fallback_by_major = {report["label"]: report for report in fallback_reports}
                    fallback_major_names = (set(fallback_by_major) - current_major_names) | zero_course_majors
                    if fallback_major_names:
                        print(
                            f"FALLBACK CHECK | worker={task_index + 1}/{task_count} | cc={ccc_name} | "
                            f"university={uni_name} | year={fallback_year_id} | "
                            f"candidate_majors={len(fallback_major_names)}"
                        )
                        for fallback_idx, major in enumerate(sorted(fallback_major_names), start=1):
                            report = fallback_by_major.get(major)
                            if not report:
                                print(f"FALLBACK MISSING | year={fallback_year_id} | cc={ccc_name} | university={uni_name} | major={major}")
                                continue
                            detail, changed = save_if_changed(api, fallback_year_id, ccc["id"], uni["id"], report)
                            course_count = articulated_course_count(detail)
                            if changed:
                                total_saved += 1
                                cc_majors_saved += 1
                                cc_courses_count += course_count
                                saved_for_this_uni += 1
                                print(
                                    f"FALLBACK SAVED | year={fallback_year_id} | cc={ccc_name} | "
                                    f"university={uni_name} | major={major} | courses={course_count} | "
                                    f"progress={fallback_idx}/{len(fallback_major_names)}"
                                )
                                time.sleep(delay_seconds)

                print(
                    f"PAIR COMPLETE | worker={task_index + 1}/{task_count} | "
                    f"global_cc={real_idx}/{total_ccs} | cc={ccc_name} | university={uni_name} | "
                    f"downloaded={saved_for_this_uni} | current_year_no_course={len(zero_course_majors)}"
                )

            except Exception as e:
                print(
                    f"PAIR ERROR | worker={task_index + 1}/{task_count} | "
                    f"global_cc={real_idx}/{total_ccs} | cc={ccc_name} | university={uni_name} | "
                    f"error={type(e).__name__} | message={e}"
                )
                continue

        completed_ccs += 1
        print(
            f"CC COMPLETE | worker={task_index + 1}/{task_count} | "
            f"global_cc={real_idx}/{total_ccs} | worker_cc={completed_ccs}/{assigned_ccs} | "
            f"name={ccc_name} | downloaded={cc_majors_saved} | courses={cc_courses_count}"
        )

    elapsed = (time.time() - start_time) / 60
    print(
        f"RUN COMPLETE | worker={task_index + 1}/{task_count} | "
        f"worker_ccs_completed={completed_ccs}/{assigned_ccs} | total_ccs={total_ccs} | "
        f"downloaded={total_saved} | duration_minutes={elapsed:.1f}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape transfer agreements from Assist.org")
    parser.add_argument(
        "--source-school-id",
        type=int,
        default=None,
        help="Filter to a specific CC source school ID (e.g. 113 for De Anza College)",
    )
    parser.add_argument(
        "--source-school-ids",
        type=int,
        nargs="+",
        default=None,
        help="Filter to an explicit list of community college source IDs",
    )
    parser.add_argument(
        "--year-id",
        type=int,
        default=77,
        help="Academic year ID (default: 77; uses year 76 for missing or non-articulated results)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Delay between downloads in seconds (default: 0.8)",
    )

    args = parser.parse_args()
    scrape_all_agreements(
        year_id=args.year_id,
        delay_seconds=args.delay,
        source_school_id=args.source_school_id,
        source_school_ids=args.source_school_ids,
    )
