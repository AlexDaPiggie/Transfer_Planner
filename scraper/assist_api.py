import time

import requests #for scraping Assist.org api

BASE_URL = "https://assist.org"

class AssistAPI:
    MAX_ATTEMPTS = 5
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self):
        """This is to fake the ID of the scraper bot"""
        self.session = requests.Session()
        self.session.headers.update ({
            "User-Agent": "Mozilla/5.0(Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/plain, */*",
            "Referer": BASE_URL,
        })
        self._init_session()

    def refresh_session(self):
        """This is to refresh the scraping session to bypass the 429 flag"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/plain, */*",
            "Referer": BASE_URL,
        })
        self._init_session()

    def _init_session(self):
        """This is to get to the homepage to get required XSRF session token"""
        self._request(BASE_URL, timeout=10)
        token = self.session.cookies.get("X-XSRF-TOKEN") or self.session.cookies.get("XSRF-TOKEN")
        if token:
            self.session.headers["X-XSRF-TOKEN"] = token

    def _request(self, url: str, **kwargs):
        """Make a request and retry temporary failures with backoff."""
        last_error = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = self.session.get(url, **kwargs)
                if response.status_code in self.RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except requests.RequestException as error:
                last_error = error
                response = getattr(error, "response", None)
                status_code = getattr(response, "status_code", None)
                retryable = status_code in self.RETRYABLE_STATUS_CODES or response is None
                if not retryable or attempt == self.MAX_ATTEMPTS - 1:
                    raise
                wait_seconds = min(30, 2 ** attempt)
                time.sleep(wait_seconds)
        raise last_error

    def get_academic_years(self):
        """This func is to fetch academic year from assist.org"""
        res = self._request(f"{BASE_URL}/api/AcademicYears", timeout=10)
        return res.json()

    def get_institutions(self):
        """This func is to fetch CCs, UCs, CSUs info"""
        res = self._request(f"{BASE_URL}/api/institutions", timeout=10)
        return res.json()

    def get_agreements_list(
        self,
        year_id: int,
        sending_id: int,
        receiving_id: int,
    ):
        
        """This is to fetch major and course keys from CCs, UCs"""
        res = self._request(
            f"{BASE_URL}/api/agreements",
            params={
                "receivingInstitutionId": receiving_id,
                "sendingInstitutionId": sending_id,
                "academicYearId": year_id,
                "categoryCode": "major",
            },
            timeout=10,
        )
        return res.json().get("reports", [])

    def get_agreement_details(self, key: str):
        """To fetch full data file for one major's transfer aggreement
        (rule showing with CC's course counts as which UC's course)"""

        res = self._request(
            f"{BASE_URL}/api/articulation/Agreements",
            params={"key": key},
            timeout=15,
        )
        return res.json().get("result", {})
