"""Regression tests for Merge AI's answer routing.

Run locally: python -m unittest discover -s tests -v
Does not call any external API and does not need credentials.
"""
import unittest

from about_merge_ai import answer_project_question
from merge_ai import build_merge_prompt, is_draft_comparison


class AnswerRoutingTests(unittest.TestCase):
    def test_creator_question(self):
        self.assertIn("Khalid Bin Ashraf", answer_project_question("Who created Merge AI?"))

    def test_purpose_question(self):
        self.assertIn("science fair", answer_project_question("Why were you created?"))

    def test_normal_questions_not_creator(self):
        for question in (
            "What is the capital of Japan?",
            "Hi, I am a seventh-grade student.",
            "What do you remember about me?",
            "Explain artificial intelligence in one sentence.",
        ):
            self.assertIsNone(answer_project_question(question))

    def test_pasted_test_list_not_creator_shortcut(self):
        questions = (
            "1. What is the capital of Japan?\n"
            "2. Who created Merge AI?\n"
            "3. Translate good morning into Spanish?"
        )
        self.assertIsNone(answer_project_question(questions))

    def test_old_comparison_replies_rejected(self):
        old_replies = (
            "Both drafts correctly identify your details.",
            "Here's a side-by-side look: Groq-style draft versus Gemini-style draft.",
            "Draft greetings: GROQ draft and GEMINI draft.",
        )
        for result in old_replies:
            self.assertTrue(is_draft_comparison(result), result)

    def test_normal_reply_is_not_comparison(self):
        self.assertFalse(is_draft_comparison("Tokyo is the capital of Japan."))

    def test_merge_prompt_uses_latest_message(self):
        prompt = build_merge_prompt(
            "Earlier conversation:\nassistant: Welcome!\nCurrent question:\nWhat is the capital of Japan?",
            {"groq": "Tokyo.", "gemini": "Tokyo."},
            "",
        )
        self.assertIn("LATEST USER MESSAGE (answer this):\nWhat is the capital of Japan?", prompt)
        self.assertNotIn("GROQ DRAFT", prompt)


if __name__ == "__main__":
    unittest.main()
