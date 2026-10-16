import requests
import json

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})

# Get XSRF token
s.get("https://assist.org", timeout=30)
token = s.cookies.get("X-XSRF-TOKEN") or s.cookies.get("XSRF-TOKEN")
if token:
    s.headers["X-XSRF-TOKEN"] = token

inst = s.get("https://assist.org/api/institutions", timeout=30).json()

cccs = [i for i in inst if i.get("isCommunityCollege")]
unis = [i for i in inst if not i.get("isCommunityCollege")]

for cc in cccs[:5]:
    for uni in unis[:5]:
        url = f"https://assist.org/api/agreements?receivingInstitutionId={uni['id']}&sendingInstitutionId={cc['id']}&academicYearId=75&categoryCode=major"
        res = s.get(url, timeout=30)
        reports = res.json().get("reports", [])
        if reports:
            print("Found route:", cc["names"][0]["name"], "->", uni["names"][0]["name"])
            print("Sample Report:")
            print(json.dumps(reports[0], indent=2))
            exit()
