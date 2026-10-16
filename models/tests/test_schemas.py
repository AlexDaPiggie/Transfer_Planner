import unittest

from models.src.schemas import CourseRow, TechnicalPlanInput


class SchemaTests(unittest.TestCase):
    def test_input_requires_official_url(self):
        with self.assertRaises(ValueError):
            CourseRow(course_code="MATH 1A", course_name="Calculus", targets=["UC Davis"])

    def test_plan_input_accepts_verified_matrix(self):
        plan = TechnicalPlanInput(
            matrix=[CourseRow(course_code="MATH 1A", course_name="Calculus", targets=["UC Davis"], official_url="https://assist.org/example")]
        )
        self.assertEqual(plan.matrix[0].course_code, "MATH 1A")
