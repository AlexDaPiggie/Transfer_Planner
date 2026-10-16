import unittest

from models.src.prompts import PLANNER_SYSTEM_PROMPT, build_chat_messages
from models.src.schemas import ChatInput


class PromptTests(unittest.TestCase):
    def test_planner_prompt_requires_evidence_bound_answers(self):
        self.assertIn("Do not invent", PLANNER_SYSTEM_PROMPT)

    def test_chat_history_is_clipped_to_six_messages(self):
        request = ChatInput(plan_context="Verified plan", message="Help", history=[{"role": "user", "content": str(i)} for i in range(8)])
        messages = build_chat_messages(request)
        self.assertEqual(len(messages), 8)  # system + six history messages + current message
