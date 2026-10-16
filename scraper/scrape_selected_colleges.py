"""Scrape only De Anza, Foothill, and West Valley for Assist year 77."""

from scraper.scrape_all import scrape_all_agreements

YEAR_ID = 77
COMMUNITY_COLLEGE_IDS = [113, 51, 80]


if __name__ == "__main__":
    scrape_all_agreements(
        year_id=YEAR_ID,
        source_school_ids=COMMUNITY_COLLEGE_IDS,
    )
