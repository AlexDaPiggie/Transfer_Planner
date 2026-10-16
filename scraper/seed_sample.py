from scraper.assist_api import AssistAPI
from scraper.sync_db import init_db, save_agreement

def seed_sample_data():
    init_db()
    api = AssistAPI()
    year_id  = 75 #the code for 2024-2025
    de_anza_id = 113 

    targets = [
        {"id": 79, "name": "UC Berkeley"},
        {"id": 39, "name": "San Jose State University"},
    ]

    for target in targets:
        print (f"Fetching agreements for De Anza -> {target['name']}...")
        reports = api.get_agreements_list(year_id, de_anza_id, target["id"])
        cs_report = next((r for r in reports if "Computer Science" in r["label"]), reports[0])
        print (f"Downloading: {cs_report['label']}...")
        detail = api.get_agreement_details(cs_report["key"])
        save_agreement(
            year_id, 
            de_anza_id, 
            target["id"], 
            cs_report["label"], 
            detail,
        )
        print (f"Saved {cs_report['label']} to transfer.db")

    print ("\nSample seed complete! transfer.db is ready.")

if __name__ == "__main__":
    seed_sample_data()

