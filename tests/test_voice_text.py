"""Speech preparation is deterministic and preserves the written answer."""
import unittest

from voice_text import UnsafeSpeechText, browser_chunks, check_final_answer, prepare_speech_text


class SpeechTextTests(unittest.TestCase):
    def test_markdown_and_original_answer(self):
        original = "The capital of **Japan** is Tokyo."
        self.assertEqual(prepare_speech_text(original), "The capital of Japan is Tokyo.")
        self.assertEqual(original, "The capital of **Japan** is Tokyo.")

    def test_headings_lists_and_multiline(self):
        text = "## Facts\n- First fact\n- [x] Second fact\n1. Third fact\n> A quotation"
        self.assertEqual(prepare_speech_text(text), "Facts\nFirst fact\nSecond fact\nThird fact\nA quotation")

    def test_links_keep_labels_not_destinations(self):
        text = "Read [NASA](https://nasa.gov/example(a)) or https://example.org."
        result = prepare_speech_text(text)
        self.assertIn("NASA", result)
        self.assertNotIn("https", result)
        self.assertNotIn("example", result)

    def test_reference_and_angle_urls(self):
        self.assertEqual(prepare_speech_text("Sources\n[1]: https://example.org\n<https://example.org>"), "Sources")

    def test_numbers_and_punctuation(self):
        result = prepare_speech_text("**$1,234.56**, 3.14, -12.5°C, 50%, 2026-11-03!!! Really???")
        self.assertEqual(result, "$1,234.56, 3.14, -12.5°C, 50%, 2026-11-03! Really?")

    def test_long_answer_and_browser_chunks_preserve_every_word(self):
        text = " ".join(f"Fact {n}: value {n}.125." for n in range(1000))
        spoken = prepare_speech_text(text)
        self.assertEqual(spoken, text)
        self.assertEqual("".join(browser_chunks(spoken)), text)
        self.assertTrue(all(".125" in chunk or not chunk.strip() for chunk in browser_chunks(spoken)))

    def test_browser_chunk_does_not_split_decimal_or_long_token(self):
        text = "This costs $100.25 and " + "x" * 300 + " exactly."
        chunks = browser_chunks(text, maximum=30)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(any("$100.25" in chunk for chunk in chunks))

    def test_code_is_not_spoken(self):
        for fence in ("```", "~~~"):
            text = f"Here is a solution:\n{fence}python\nprint('secret code')\n{fence}\nIt prints a message."
            self.assertEqual(prepare_speech_text(text), "Here is a solution:\nA code example is available in the chat.\nIt prints a message.")

    def test_unclosed_code_and_reasoning(self):
        self.assertNotIn("private", prepare_speech_text("Answer. <think>private"))
        self.assertNotIn("hidden", prepare_speech_text("Answer.\n```python\nhidden()"))
        self.assertEqual(prepare_speech_text("<thinking>private</thinking>Final."), "Final.")

    def test_inline_code_emphasis_and_html(self):
        self.assertEqual(prepare_speech_text("Use `pip` with *care* and <b>attention</b> &amp; _patience_."), "Use pip with care and attention & patience.")

    def test_table_preserves_values(self):
        text = "| Item | Amount |\n|---|---:|\n| Rain | 12.5 mm |\n| Snow | 0.5 cm |"
        self.assertEqual(prepare_speech_text(text), "Item; Amount\nRain; 12.5 mm\nSnow; 0.5 cm")

    def test_empty(self):
        for value in (None, "", "  \n", "---", "<https://example.org>"):
            self.assertEqual(prepare_speech_text(value), "")
        self.assertEqual(browser_chunks(""), [])

    def test_provider_drafts_are_blocked_at_speech_boundary(self):
        for text in (
            "Gemini says rain is water. Groq says condensation.",
            "Both drafts agree on Tokyo.",
            "Private evidence note: uncertain.",
            "| Provider | Answer |\n| Gemini | One |\n| Groq | Two |",
        ):
            with self.subTest(text=text), self.assertRaises(UnsafeSpeechText):
                check_final_answer(text)

    def test_normal_answers_and_public_capability_comparisons_allowed(self):
        for text in (
            "Rain forms when cloud droplets grow heavy enough to fall.",
            "The evidence is mixed; we cannot determine the exact location.",
            "| Service | Type |\n| Gemini | Model family |\n| Groq | Inference service |",
        ):
            check_final_answer(text)


if __name__ == "__main__":
    unittest.main()
