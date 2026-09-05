import time 
from scraper.assist_api import AssistAPI
from scraper.sync_db import init_db, save_agreement, get_db_connection
import os
from dotenv import load_dotenv
import json
import sys
import subprocess

load_dotenv(override=True)

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

def scrape_all_agreements(
    year_id: int = 75, 
    delay_seconds: float = 0.8,
):

    init_db()
    api = AssistAPI()

    institutions = api.get_institutions()
    ccc_schools = [i for i in institutions if i.get("isCommunityCollege", False)]
    uni_schools = [i for i in institutions if not i.get("isCommunityCollege", False)]

    total_ccs = len(ccc_schools)
    total_saved = 0
    start_time = time.time()

    print(f"Starting scrape all: {total_ccs} CCs -> {len(uni_schools)} Universities (Year {year_id})")

    for ccc in ccc_schools:
        ccc_name = ccc["names"][0]["name"]

        #Update the starting ids of cc from the current progress
        real_idx = ccc_schools.index(ccc) + 1
        pct = (real_idx / total_ccs) * 100
        print(f"\n\n>>{real_idx}/{total_ccs} - Begin to scrape CC: {ccc_name}")

        cc_majors_saved = 0
        cc_courses_count = 0

        #Update the starting ids  of the universities from the current progresss

        for uni in uni_schools:
            uni_name = uni["names"][0]["name"]
            try:
                reports = api.get_agreements_list(year_id, ccc["id"], uni["id"])
                if not reports:
                    remove_dead_route(
                        year_id,
                        ccc["id"],
                        uni["id"],
                    )
                    continue
                #Clean up the dead majors in the scraping process
                offical_majors = [r["label"] for r in reports]

                remove_dead_majors(
                    year_id,
                    ccc["id"],
                    uni["id"],
                    offical_majors
                )

                print(f"  -> {uni_name} ({len(reports)} majors found):")
                saved_for_this_uni = 0
                update_needed = 0
                majors_to_download = []
                
                #Check what course has been changed
                for report in reports:
                    major = report["label"]
                    api_key = report["key"]
                    if not is_up_to_date(
                        year_id,
                        ccc["id"],
                        uni["id"],
                        major,
                        api_key,
                    ):
                        update_needed += 1
                        majors_to_download.append(report)

                #dwonload the updates in a loop
                for report_idx, report in enumerate(majors_to_download, start = 1):
                    major = report["label"]
                    api_key = report["key"]
                    detail = fetch_with_retry(api, api_key)
                    save_agreement(
                        year_id,
                        ccc["id"],
                        uni["id"],
                        major,
                        api_key,
                        detail
                    )

                    raw_art = detail.get("articulations", "[]")
                    courses_in_major = raw_art.count('"type":"Course"') if isinstance(raw_art, str) else 0

                    total_saved += 1
                    cc_majors_saved += 1
                    cc_courses_count += courses_in_major
                    saved_for_this_uni += 1

                    print(f"     [{report_idx}/{len(reports)}] Saved: {major} (~{courses_in_major} courses) | Total DB: {total_saved} | [{real_idx}/{total_ccs} - {pct:.1f}%] Scraping CC: {ccc_name}")
                    time.sleep(delay_seconds)

            except Exception as e:
                print(f"  Error scraping {ccc_name} -> {uni_name}: {e}")
                continue

        print(f"  \n\n>>> Summary for {ccc_name}: {cc_majors_saved} new majors saved (~{cc_courses_count} courses) | Total DB: {total_saved}")

    elapsed = (time.time() - start_time) / 60
    print(f"\n=== DONE! Saved {total_saved} agreements across {total_ccs} CCs in {elapsed:.1f} mins ===")


if __name__ == "__main__":
    scrape_all_agreements()