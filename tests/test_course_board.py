import unittest

from backend.model_planner.course_board import build_course_board


class CourseBoardTests(unittest.TestCase):
    def test_shared_course_preserves_required_and_recommended_roles_per_goal(self):
        def agreement(target_id, target_name, heading):
            return {
                "source_id": 113, "source_name": "De Anza College", "target_id": target_id,
                "target_name": target_name, "major": "Computer Science", "year_id": 77,
                "document_key": "example", "payload": {
                    "templateAssets": [{"content": f"{heading} MATH 101"}],
                    "articulations": [{"articulation": {
                        "course": {"prefix": "MATH", "courseNumber": "101", "courseTitle": "Calculus"},
                        "sendingArticulation": {"items": [{"items": [{"type": "Course", "prefix": "MATH", "courseNumber": "1A", "courseTitle": "Calculus", "minUnits": 5}]}]},
                    }}],
                },
            }

        agreements = [agreement(1, "University A", "Required courses"), agreement(2, "University B", "Strongly recommended courses")]
        for ordered in (agreements, list(reversed(agreements))):
            board = build_course_board(ordered, 77, [113], 113)
            self.assertEqual(len(board["required"]), 1)
            self.assertEqual(board["recommended"], [])
            self.assertEqual({goal["category"] for goal in board["required"][0]["goals"]}, {"required", "recommended"})
            self.assertEqual(board["required"][0]["supports_count"], 2)

    def test_unarticulated_requirement_is_shown_in_its_own_column(self):
        agreement = {
            "source_id": 113,
            "source_name": "De Anza College",
            "target_id": 7,
            "target_name": "Example University",
            "major": "Design",
            "year_id": 77,
            "document_key": "agreement-key",
            "payload": {
                "articulations": [{
                    "articulation": {
                        "course": {
                            "prefix": "DES",
                            "courseNumber": "101",
                            "courseTitle": "Design Foundations",
                        },
                        "sendingArticulation": {
                            "items": [],
                            "noArticulationReason": "No articulated course is available.",
                        },
                    },
                }],
            },
        }

        board = build_course_board([agreement], 77, [113], 113)

        self.assertEqual(board["required"], [])
        self.assertEqual(board["recommended"], [])
        self.assertEqual(len(board["not_articulated"]), 1)
        unavailable = board["not_articulated"][0]
        self.assertEqual(unavailable["course_code"], "DES 101")
        self.assertEqual(unavailable["reason"], "No articulated course is available.")
        self.assertEqual(unavailable["supports_count"], 1)

    def test_requirement_with_an_option_at_any_selected_college_is_not_unavailable(self):
        base = {
            "target_id": 7,
            "target_name": "Example University",
            "major": "Design",
            "year_id": 77,
            "document_key": "agreement-key",
        }
        no_option = {
            **base,
            "source_id": 113,
            "source_name": "De Anza College",
            "payload": {"articulations": [{"articulation": {
                "course": {"prefix": "DES", "courseNumber": "101", "courseTitle": "Design Foundations"},
                "sendingArticulation": {"items": []},
            }}]},
        }
        with_option = {
            **base,
            "source_id": 114,
            "source_name": "Foothill College",
            "payload": {"articulations": [{"articulation": {
                "course": {"prefix": "DES", "courseNumber": "101", "courseTitle": "Design Foundations"},
                "sendingArticulation": {"items": [{"items": [{
                    "type": "Course", "prefix": "ART", "courseNumber": "1",
                    "courseTitle": "Introduction to Art", "minUnits": 4,
                }]}]},
            }}]},
        }

        board = build_course_board([no_option, with_option], 77, [113, 114], 113)

        self.assertEqual(board["not_articulated"], [])


if __name__ == "__main__":
    unittest.main()
