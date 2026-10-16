"""One-time or repeatable Assist institution-name sync for the planner catalog."""
from scraper.assist_api import AssistAPI
from scraper.sync_db import init_db, save_institutions

def main() -> None:
    init_db()
    institutions = AssistAPI().get_institutions()
    save_institutions(institutions)
    print(f"Synced {len(institutions)} institution names.")

if __name__ == "__main__":
    main()
