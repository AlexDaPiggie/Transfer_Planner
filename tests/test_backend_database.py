import json
import unittest
from unittest.mock import patch

from backend.model_planner.main import (
    ChatRequest,
    PlanRequest,
    TargetSelection,
    api_chat,
    api_generate_plan,
    api_health,
    list_sources,
)
from models.src.schemas import TechnicalPlan
from scraper.sync_db import normalize_database_url


class FakeCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params):
        self.queries.append((query, params))

    def fetchone(self):
        payload = {"articulations": [{"articulation": {"course": {"prefix": "MATH", "courseNumber": "1"}, "sendingArticulation": {"items": [{"items": [{"type": "Course", "prefix": "MATH", "courseNumber": "1A", "courseTitle": "Calculus", "minUnits": 5}]}]}}}]}
        return (json.dumps(payload), "document-key")

    def fetchall(self):
        return [(113, "De Anza College")]


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance

    def close(self):
        pass


class BackendDatabaseTests(unittest.TestCase):
    def test_health_endpoint_does_not_require_the_database(self):
        self.assertEqual(api_health(), {"status": "ok"})

    def test_normalize_database_url_removes_quotes_from_sslmode(self):
        url = 'postgresql://user:password@host/db?sslmode="verify-full"'
        self.assertEqual(
            normalize_database_url(url),
            "postgresql://user:password@host/db?sslmode=verify-full",
        )

    def test_backend_reads_postgres_raw_json_column(self):
        connection = FakeConnection()
        request = PlanRequest(
            year_id=75,
            source_ids=[1],
            targets=[TargetSelection(target_id=2, target_name="University", major="Computer Science")],
        )

        with patch("backend.model_planner.main.get_db_connection", return_value=connection), \
             patch("backend.model_planner.main.generate_technical_plan") as planner, \
             patch("backend.model_planner.main.generate_student_summary", return_value="Summary"):
            planner.return_value = TechnicalPlan(summary="Technical", course_priorities=["MATH 1A"], warnings=["Verify"], source_urls=["https://assist.org"])
            api_generate_plan(request)

        query = connection.cursor_instance.queries[0][0]
        self.assertIn("raw_json", query)
        self.assertNotIn("raw_payload", query)

    def test_sources_are_loaded_from_agreement_rows(self):
        connection = FakeConnection()
        with patch("backend.model_planner.main.get_db_connection", return_value=connection):
            sources = list_sources(75)
        self.assertEqual(sources[0]["id"], 113)
        query = connection.cursor_instance.queries[0][0]
        self.assertIn("source_school_id", query)
        self.assertIn(") AS sources", query)

    def test_chat_uses_the_standalone_explainer_model(self):
        request = ChatRequest(plan_context="Verified plan", history=[], message="What transfers?")
        with patch("backend.model_planner.main.answer_student_question") as chat:
            chat.return_value.model_dump.return_value = {"reply": "Check Assist.org."}
            response = api_chat(request)
        self.assertEqual(response["reply"], "Check Assist.org.")


if __name__ == "__main__":
    unittest.main()
