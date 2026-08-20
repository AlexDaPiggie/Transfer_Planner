import requests #for scraping Assist.org api

BASE_URL = "https://assist.org"

class AssistAPI:
    def __init__(self):
        """This is to fake the ID of the scraper bot"""
        self.session = requests.Session()
        self.session.headers.update ({
            "User-Agent": "Mozilla/5.0(Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/plain, */*",
            "Referer": BASE_URL,
        })
        self._init_session()

    def _init_session(self):
        """This is to get to the homepage to get required XSRF session token"""
        self.session.get(BASE_URL, timeout = 10)
        token = self.session.cookies.get("X-XSRF-TOKEN") or self.session.cookies.get("XSRF-TOKEN")
        if token:
            self.session.headers["X-XSRF-TOKEN"] = token
        

    def get_academic_years(self):
        """This func is to fetch academic year from assist.org"""
        res = self.session.get(f"{BASE_URL}/api/AcademicYears", timeout = 10)
        res.raise_for_status() #Check if the request is sucessful or not
        return res.json()

    def get_institutions(self):
        """This func is to fetch CCs, UCs, CSUs info"""
        res = self.session.get(f"{BASE_URL}/api/institutions", timeout = 10)
        res.raise_for_status() #Check if the request is sucessful or not
        return res.json()

    def get_agreements_list(
        self,
        year_id: int,
        sending_id: int,
        receiving_id: int,
    ):
        
        """This is to fetch major and course keys from CCs, UCs"""
        url = f"{BASE_URL}/api/agreements?receivingInstitutionId={receiving_id}&sendingInstitutionId={sending_id}&academicYearId={year_id}&categoryCode=major"
        res = self.session.get(url, timeout = 10)
        res.raise_for_status()
        return res.json().get("reports", [])

    def get_agreement_details(self, key: str):
        """To fetch full data file for one major's transfer aggreement
        (rule showing with CC's course counts as which UC's course)"""

        url = f"{BASE_URL}/api/articulation/Agreements?key={key}"
        res = self.session.get(url, timeout=15)
        res.raise_for_status()
        return res.json().get("result", {})