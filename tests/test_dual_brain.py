"""Offline tests for Merge AI's dual-brain orchestration."""
import unittest
from unittest.mock import patch

from dual_brain import DualBrain, _text_from_anthropic, _text_from_openai


class DualBrainTests(unittest.TestCase):
    def test_openai_response_text(self):
        self.assertEqual(_text_from_openai({
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": "hello"}
            ]}]
        }), "hello")

    def test_claude_response_text(self):
        self.assertEqual(_text_from_anthropic({
            "content": [{"type": "text", "text": "hello"}]
        }), "hello")

    def test_automatic_lead_routing(self):
        self.assertEqual(DualBrain.choose_lead("Debug this Python API"), "openai")
        self.assertEqual(DualBrain.choose_lead("Rewrite this essay"), "claude")

    def test_requires_both_keys_to_activate(self):
        self.assertFalse(DualBrain(openai_key="x", anthropic_key="").configured)

    def test_both_models_collaborate_and_synthesize(self):
        brain = DualBrain(openai_key="o", anthropic_key="c")
        calls = []
        def fake(provider, prompt, system, tokens):
            calls.append(provider)
            if "Produce ONE final answer" in prompt:
                return "Final merged answer"
            return provider + " proposal"
        with patch.object(brain, "_call", side_effect=fake):
            answer, report = brain.answer(
                "Explain gravity", [{"role": "user", "content": "Explain gravity"}]
            )
        self.assertEqual(answer, "Final merged answer")
        self.assertIn("openai", calls)
        self.assertIn("claude", calls)
        self.assertEqual(report["mode"], "dual_brain")
        self.assertEqual(report["providers"]["openai"], "success")
        self.assertEqual(report["providers"]["claude"], "success")

    def test_deep_mode_runs_cross_reviews(self):
        brain = DualBrain(openai_key="o", anthropic_key="c")
        calls = []
        def fake(provider, prompt, system, tokens):
            calls.append((provider, prompt))
            if "Produce ONE final answer" in prompt:
                return "Deep merged answer"
            if "Critically review" in prompt:
                return "Review completed"
            return provider + " proposal"
        with patch.object(brain, "_call", side_effect=fake):
            answer, report = brain.answer(
                "Explain gravity", [{"role": "user", "content": "Explain gravity"}],
                deep=True
            )
        self.assertEqual(answer, "Deep merged answer")
        self.assertEqual(report["reviews_completed"], 2)


if __name__ == "__main__":
    unittest.main()
