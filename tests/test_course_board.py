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
    @staticmethod
    def _chem_course(prefix, number, course_id, sending=None):
        articulation = {
            "course": {"prefix": prefix, "courseNumber": number, "courseIdentifierParentId": course_id, "courseTitle": f"University {number}"},
            "sendingArticulation": {"items": []},
        }
        if sending:
            articulation["sendingArticulation"]["items"] = [{"items": [{
                "type": "Course", "prefix": "CHEM", "courseNumber": code,
                "courseTitle": f"Chemistry {code}", "minUnits": 5,
            } for code in sending]}]
        else:
            articulation["sendingArticulation"]["noArticulationReason"] = "No Course Articulated"
        return {"articulation": articulation}

    @staticmethod
    def _chem_series(sending):
        return {"articulation": {
            "series": {"name": "CHEM 1A, CHEM 1AL, CHEM 1B", "courses": [
                {"prefix": "CHEM", "courseNumber": "1A", "courseIdentifierParentId": 1, "courseTitle": "University 1A"},
                {"prefix": "CHEM", "courseNumber": "1AL", "courseIdentifierParentId": 2, "courseTitle": "University 1AL"},
                {"prefix": "CHEM", "courseNumber": "1B", "courseIdentifierParentId": 3, "courseTitle": "University 1B"},
            ]},
            "sendingArticulation": {"items": [{"items": [{
                "type": "Course", "prefix": "CHEM", "courseNumber": code,
                "courseTitle": f"Chemistry {code}", "minUnits": 5,
            } for code in sending]}]},
        }}

    @staticmethod
    def _chem_agreement(source_id, source_name, articulations):
        return {
            "source_id": source_id,
            "source_name": source_name,
            "target_id": 7,
            "target_name": "Example University",
            "major": "Chemistry",
            "year_id": 77,
            "document_key": "agreement-key",
            "payload": {
                "templateAssets": [{"type": "GeneralText", "content": "Major requirements"}],
                "articulations": articulations,
            },
        }

    def test_complete_main_series_suppresses_split_fallback_rows(self):
        agreements = [
            self._chem_agreement(113, "De Anza College", [self._chem_series(["1A", "1B", "1C"])]),
            self._chem_agreement(51, "Foothill College", [
                self._chem_course("CHEM", "1A", 1, ["1A", "1B"]),
                self._chem_course("CHEM", "1AL", 2, ["1AL"]),
                self._chem_course("CHEM", "1B", 3, ["1B", "1C"]),
            ]),
        ]

        board = build_course_board(agreements, 77, [113, 51], 113)

        groups = board["universities"][0]["required"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["source_name"], "De Anza College")
        self.assertEqual([course["code"] for course in groups[0]["options"][0]["courses"]], ["CHEM 1A", "CHEM 1B", "CHEM 1C"])
        self.assertEqual({course["source_name"] for course in board["required"]}, {"De Anza College"})

    def test_fallback_is_used_when_main_route_has_an_unarticulated_part(self):
        agreements = [
            self._chem_agreement(113, "De Anza College", [self._chem_series([])]),
            self._chem_agreement(51, "Foothill College", [
                self._chem_course("CHEM", "1A", 1, ["1A", "1B"]),
                self._chem_course("CHEM", "1AL", 2, ["1AL"]),
                self._chem_course("CHEM", "1B", 3, ["1B", "1C"]),
            ]),
        ]

        board = build_course_board(agreements, 77, [113, 51], 113)

        groups = board["universities"][0]["required"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["source_name"], "Foothill College")
        self.assertIn("CHEM 1B", groups[0]["fallback_note"])

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

    def test_assist_one_following_advisement_becomes_switchable_course_options(self):
        def articulation(code, cell_id, cc_codes):
            sending_sets = [cc_codes]
            if code == "3":
                sending_sets = [["C1"], ["C2"]]
            return {"templateCellId": cell_id, "articulation": {
                "course": {"prefix": "UNI", "courseNumber": code, "courseIdentifierParentId": cell_id, "courseTitle": code},
                "sendingArticulation": {"items": [{"courseConjunction": "And", "items": [
                    {"type": "Course", "prefix": "CC", "courseNumber": cc_code, "courseTitle": cc_code, "minUnits": 3}
                    for cc_code in sending_set
                ]} for sending_set in sending_sets]},
            }}

        row_specs = [
            ("cell-a", "1", ["A1"]),
            ("cell-b", "2", ["B1", "B2"]),
            ("cell-c", "3", ["C1"]),
        ]
        rows = [{"cells": [{
            "type": "Course",
            "id": cell_id,
            "course": {"prefix": "UNI", "courseNumber": code, "courseIdentifierParentId": cell_id},
        }]} for cell_id, code, _ in row_specs]
        agreement = self._chem_agreement(113, "De Anza College", [
            articulation(code, cell_id, cc_codes) for cell_id, code, cc_codes in row_specs
        ])
        agreement["payload"]["templateAssets"] = [
            {"type": "GeneralText", "content": "Major requirements"},
            {"type": "RequirementGroup", "sections": [{
                "rows": rows,
                "advisements": [{"type": "NFollowing", "amount": 1, "amountUnitType": "Course", "selectionType": "Complete"}],
            }]},
        ]

        board = build_course_board([agreement], 77, [113], 113)

        university = board["universities"][0]
        self.assertEqual(len(university["required"]), 1)
        group = university["required"][0]
        self.assertEqual(len(group["choices"]), 3)
        self.assertEqual([course["code"] for course in group["options"][0]["courses"]], ["CC A1"])
        self.assertEqual([choice["target_course"] for choice in group["choices"]], ["UNI 1", "UNI 2", "UNI 3"])
        self.assertEqual([course["code"] for course in group["choices"][1]["options"][0]["courses"]], ["CC B1", "CC B2"])
        self.assertEqual([option["label"] for option in group["choices"][2]["options"]], ["Option 1 of 2", "Option 2 of 2"])
        self.assertEqual(group["options"], group["choices"][0]["options"])
        self.assertEqual({course["course_code"] for course in board["required"]}, {"CC A1"})

    def test_one_main_college_choice_prevents_filling_other_choices_from_fallback(self):
        cell_ids = ["cell-a", "cell-b"]

        def agreement(source_id, source_name, articulated_codes):
            source_cell_ids = [f"{source_id}-{cell_id}" for cell_id in cell_ids]
            articulations = []
            for index, cell_id in enumerate(source_cell_ids):
                code = str(index + 1)
                sending = [{"type": "Course", "prefix": "CC", "courseNumber": f"{source_id}{code}", "minUnits": 3}] if code in articulated_codes else []
                articulations.append({"templateCellId": cell_id, "articulation": {
                    "course": {"prefix": "UNI", "courseNumber": code, "courseIdentifierParentId": cell_id},
                    "sendingArticulation": {"items": [{"items": sending}]},
                }})
            result = self._chem_agreement(source_id, source_name, articulations)
            result["payload"]["templateAssets"] = [
                {"type": "GeneralText", "content": "Major requirements"},
                {"type": "RequirementGroup", "sections": [{
                    "rows": [{"cells": [{"id": cell_id, "type": "Course", "course": {"prefix": "UNI", "courseNumber": str(index + 1)}}]} for index, cell_id in enumerate(source_cell_ids)],
                    "advisements": [{"type": "NFollowing", "amount": 1, "amountUnitType": "Course"}],
                }]},
            ]
            return result

        agreements = [
            agreement(113, "De Anza College", {"1"}),
            agreement(51, "Foothill College", {"1", "2"}),
        ]
        board = build_course_board(agreements, 77, [113, 51], 113)

        group = board["universities"][0]["required"][0]
        self.assertEqual(group["source_name"], "De Anza College")
        self.assertEqual(len(group["options"]), 1)
        self.assertIsNone(group["fallback_note"])

        no_main_route = [agreement(113, "De Anza College", set()), agreements[1]]
        fallback_board = build_course_board(no_main_route, 77, [113, 51], 113)
        fallback_group = fallback_board["universities"][0]["required"][0]
        self.assertEqual(fallback_group["source_name"], "Foothill College")
        self.assertEqual(len(fallback_group["choices"]), 2)
        self.assertIn("does not articulate", fallback_group["fallback_note"])


if __name__ == "__main__":
    unittest.main()
