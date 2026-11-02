"""Provider-boundary regressions; all API calls are mocked, never paid requests."""
import json
import unittest
from unittest.mock import patch

from merge_ai import MergeAI, MergeAIError, Provider, ProviderError, final_text, build_merge_prompt


class SynthesisTests(unittest.TestCase):
    def engine(self, **kwargs):
        return MergeAI(tuple(Provider(n, "test", "test-model") for n in ("gemini", "groq", "openrouter")),
                       tavily_api_key="test", brave_api_key="", **kwargs)

    @patch("merge_ai.call_provider")
    @patch("merge_ai.search_tavily")
    def test_greeting_is_immediate_in_both_modes(self, search, call):
        for fast in (True, False):
            self.assertEqual(self.engine().ask("Hi!", fast=fast), "Hey! How can I help you today?")
        call.assert_not_called()
        search.assert_not_called()

    @patch("merge_ai.call_provider")
    def test_identity_is_application_owner(self, call):
        self.assertEqual(self.engine().ask("Who created Merge AI?"), "Merge AI was created by Khalid.")
        call.assert_not_called()

    @patch("merge_ai.call_provider", return_value="Rain falls when condensed water droplets grow heavy enough.")
    def test_fast_uses_only_one_provider(self, call):
        result = self.engine().ask("What causes rain?", web_search=False)
        self.assertTrue(result.startswith("Rain"))
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[0].name, "groq")

    @patch("merge_ai.call_provider", return_value="One answer.")
    def test_configured_merger_is_honored(self, call):
        self.engine(merger="gemini").ask("Explain rain.", web_search=False)
        self.assertEqual(call.call_args.args[0].name, "gemini")

    def test_fast_falls_back_without_retrying_rate_limit(self):
        def provider(p, *_):
            if p.name == "groq":
                raise ProviderError("groq", "private failure detail", 429)
            return "A single answer."
        with patch("merge_ai.call_provider", side_effect=provider) as call:
            self.assertEqual(self.engine().ask("Rain?", web_search=False), "A single answer.")
            self.assertEqual([c.args[0].name for c in call.call_args_list], ["groq", "gemini"])

    def test_deep_collects_all_and_returns_only_synthesis(self):
        def provider(p, messages, _):
            if "candidate_suggestions" in messages[0]["content"]:
                return "Rain forms when cloud droplets grow heavy enough to fall."
            return {"groq": "Water condenses.", "gemini": "Droplets collide.", "openrouter": "Gravity causes rain."}[p.name]
        with patch("merge_ai.call_provider", side_effect=provider) as call:
            engine = self.engine()
            result = engine.ask("What causes rain?", fast=False, web_search=False)
            self.assertEqual(result, "Rain forms when cloud droplets grow heavy enough to fall.")
            self.assertEqual(call.call_count, 4)
            self.assertTrue(engine.last_report["merged"])
            self.assertNotIn("drafts", engine.last_report)

    def test_disagreement_reaches_synthesizer_with_uncertainty_instructions(self):
        notes = {"groq": "Kutir is in India.", "gemini": "Kutir is in Bangladesh."}
        prompt = build_merge_prompt("Where is Kutir Design and Construction?", notes, "No verified address.")
        self.assertIn("NOT evidence", prompt)
        self.assertIn("state uncertainty", prompt)
        data = json.loads(prompt.split("CONTEXT DATA (JSON):\n")[1].split("\n\nReturn")[0])
        self.assertEqual(data["candidate_suggestions"], list(notes.values()))
        engine = self.engine()
        with patch("merge_ai.call_provider", return_value="I couldn't verify which company you mean. Could you share its website?"):
            self.assertIn("couldn't verify", engine.merge_drafts("Where is Kutir?", notes, "", 1000))

    def test_deep_failure_never_returns_arbitrary_conflicting_draft(self):
        with patch("merge_ai.call_provider", side_effect=MergeAIError("unavailable")):
            with self.assertRaises(MergeAIError):
                self.engine().merge_drafts("Where?", {"groq": "India", "gemini": "Bangladesh"}, "", 1000)

    def test_provider_attribution_is_rejected_even_without_word_draft(self):
        for response in ("Gemini says rain is condensation.", "According to Groq, rain is water.",
                         "Gemini: condensation\nGroq: water", "| Gemini | Groq |\n| water | rain |",
                         "Private evidence note 1 says rain."):
            with self.subTest(response=response), self.assertRaises(MergeAIError):
                final_text(response, "What causes rain?")

    def test_comparison_and_coding_requested_by_user_are_preserved(self):
        self.assertEqual(final_text("| Gemini | Groq |\n| Google models | hosted inference |", "Compare Gemini and Groq"),
                         "| Gemini | Groq |\n| Google models | hosted inference |")
        code = '```python\nprint("Gemini says hello")\n```'
        self.assertEqual(final_text(code, "Write Python to print Gemini says hello"), code)
        self.assertEqual(final_text("| Solid | Liquid |\n| fixed | flowing |", "Compare solids and liquids"),
                         "| Solid | Liquid |\n| fixed | flowing |")

    def test_hidden_reasoning_never_reaches_display(self):
        self.assertEqual(final_text("<think>private notes</think>Tokyo.", "Japan's capital?"), "Tokyo.")
        with self.assertRaises(MergeAIError):
            final_text("<think>unfinished private notes", "Japan's capital?")

    @patch("merge_ai.call_provider", side_effect=["Gemini says X and Groq says Y.", "Clouds contain tiny droplets."])
    def test_fast_provider_leak_falls_back_to_clean_answer(self, call):
        self.assertEqual(self.engine().ask("What are clouds?", web_search=False), "Clouds contain tiny droplets.")
        self.assertEqual(call.call_count, 2)

    @patch("merge_ai.call_provider", return_value="They grow by colliding with other droplets.")
    def test_followup_context_preserved_in_fast_and_recovery(self, call):
        question = "Recent conversation:\nuser: Explain raindrops.\nassistant: Clouds hold droplets.\nCurrent question:\nHow do they grow?"
        self.engine().ask(question, web_search=False)
        self.assertIn("Explain raindrops", call.call_args.args[1][0]["content"])
        self.assertIn("How do they grow?", call.call_args.args[1][0]["content"])

    @patch("merge_ai.call_provider", return_value="Today's result is supported by the source.")
    @patch("merge_ai.search_tavily", return_value=("Official current evidence", [{"title": "Source", "url": "https://example.org"}]))
    def test_web_evidence_is_used_without_searching_private_context(self, search, call):
        engine = self.engine()
        engine.ask("Saved user preferences: private memory\nCurrent question:\nWhat happened today?")
        search.assert_called_once_with("What happened today?", "test")
        self.assertIn("Official current evidence", call.call_args.args[1][0]["content"])
        self.assertEqual(engine.last_report["sources"][0]["url"], "https://example.org")

    @patch("merge_ai.call_provider", return_value="Answer to the latest question.")
    def test_long_history_does_not_cut_off_latest_question(self, call):
        self.engine().ask("old " * 8000 + "\nCurrent question:\nExplain gravity.", web_search=False)
        self.assertIn("Explain gravity.", call.call_args.args[1][0]["content"])

    def test_disabled_providers_stay_disabled(self):
        engine = MergeAI([Provider("groq", "test", "model", enabled=False)], tavily_api_key="", brave_api_key="")
        with patch("merge_ai.call_provider") as call, self.assertRaises(MergeAIError):
            engine.ask("Rain?", web_search=False)
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
