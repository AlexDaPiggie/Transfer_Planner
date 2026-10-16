import unittest

from backend.model_planner.transfer_plan import build_assist_url, build_transfer_plan


class TransferPlannerTests(unittest.TestCase):
    def test_builds_direct_assist_link_from_saved_agreement_identity(self):
        url = build_assist_url(75, 113, 79, "major-key")
        self.assertIn("year=75", url)
        self.assertIn("institution=113", url)
        self.assertIn("agreement=79", url)
        self.assertIn("viewByKey=major-key", url)
        self.assertIn("/transfer/results?", url)
        self.assertIn("viewAgreementsOptions=true", url)

    def test_prioritizes_a_course_that_supports_more_selected_targets(self):
        agreements = [
            {"source_id": 113, "source_name": "De Anza College", "target_id": 1, "target_name": "UC Example", "major": "Computer Science", "document_key": "a", "courses": [{"code": "MATH 1A", "title": "Calculus I", "units": 5}]},
            {"source_id": 113, "source_name": "De Anza College", "target_id": 2, "target_name": "CSU Example", "major": "Computer Science", "document_key": "b", "courses": [{"code": "MATH 1A", "title": "Calculus I", "units": 5}, {"code": "PHYS 4A", "title": "Mechanics", "units": 4}]},
        ]
        plan = build_transfer_plan(agreements, 75)
        self.assertEqual(plan["recommended_courses"][0]["course_code"], "MATH 1A")
        self.assertEqual(plan["recommended_courses"][0]["supports_count"], 2)
        self.assertEqual(plan["coverage"]["selected_targets"], 2)

    def test_prioritizes_main_college_when_course_coverage_is_tied(self):
        agreements = [
            {"source_id": 113, "source_name": "De Anza College", "target_id": 1, "target_name": "UC Example", "major": "Computer Science", "document_key": "a", "courses": [{"code": "MATH 1A", "title": "Calculus I", "units": 5}]},
            {"source_id": 72, "source_name": "Foothill College", "target_id": 1, "target_name": "UC Example", "major": "Computer Science", "document_key": "b", "courses": [{"code": "MATH 1A", "title": "Calculus I", "units": 5}]},
        ]

        plan = build_transfer_plan(agreements, 75, main_source_id=113)

        self.assertEqual(plan["recommended_courses"][0]["source_id"], 113)
        self.assertTrue(plan["recommended_courses"][0]["is_main_college"])
