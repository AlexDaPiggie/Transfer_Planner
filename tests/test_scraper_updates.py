import unittest
from io import StringIO
from unittest.mock import patch

import requests

from scraper.assist_api import AssistAPI
import scraper.scrape_all as scrape_module


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.headers = {}
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class AssistAPIRetryTests(unittest.TestCase):
    def test_get_agreements_list_retries_temporary_http_errors(self):
        api = AssistAPI.__new__(AssistAPI)
        api.session = FakeSession([
            FakeResponse(503, {}),
            FakeResponse(200, {"reports": [{"label": "Computer Science", "key": "k1"}]}),
        ])

        with patch("scraper.assist_api.time.sleep"):
            reports = api.get_agreements_list(75, 1, 2)

        self.assertEqual(reports[0]["key"], "k1")
        self.assertEqual(api.session.calls, 2)

    def test_empty_agreement_list_does_not_delete_existing_records(self):
        class FakeAPI:
            def get_institutions(self):
                return [
                    {"id": 1, "isCommunityCollege": True, "names": [{"name": "Community College"}]},
                    {"id": 2, "isCommunityCollege": False, "names": [{"name": "University"}]},
                ]

            def get_agreements_list(self, year_id, sending_id, receiving_id):
                return []

        with patch.object(scrape_module, "AssistAPI", return_value=FakeAPI()), \
             patch.object(scrape_module, "init_db"), \
             patch.object(scrape_module, "remove_dead_route", side_effect=AssertionError("delete called")):
            scrape_module.scrape_all_agreements(year_id=75)

    def test_scrape_logs_global_and_worker_cc_progress(self):
        class FakeAPI:
            def get_institutions(self):
                return [
                    {"id": 1, "isCommunityCollege": True, "names": [{"name": "Community College"}]},
                    {"id": 2, "isCommunityCollege": False, "names": [{"name": "University"}]},
                ]

            def get_agreements_list(self, year_id, sending_id, receiving_id):
                return []

        output = StringIO()
        with patch.object(scrape_module, "AssistAPI", return_value=FakeAPI()), \
             patch.object(scrape_module, "init_db"), \
             patch.object(scrape_module, "remove_dead_route"), \
             patch("sys.stdout", output):
            scrape_module.scrape_all_agreements(year_id=75)

        logs = output.getvalue()
        self.assertIn("RUN START", logs)
        self.assertIn("global_cc=1/1", logs)
        self.assertIn("worker_cc=1/1", logs)
        self.assertIn("CC COMPLETE", logs)
        self.assertIn("RUN COMPLETE", logs)


if __name__ == "__main__":
    unittest.main()
