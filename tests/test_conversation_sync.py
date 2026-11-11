"""Shared request-pipeline tests; no model or cloud credentials required."""
import unittest

from conversation_pipeline import DuplicateTurnError, claim_voice_event, process_turn


class SharedPipelineTests(unittest.TestCase):
    def test_chat_and_voice_use_same_answer_callback(self):
        calls = []
        def answer(chat, question):
            calls.append(question)
            return "Final: " + question, [{"title": "source", "url": "https://example.com"}]
        chat = {"id": "c", "title": "New chat", "messages": []}
        persist_calls = []
        process_turn(chat, "typed turn", answer=answer, persist=persist_calls.append, source="chat")
        process_turn(chat, "spoken turn", answer=answer, persist=persist_calls.append, source="voice")
        self.assertEqual(calls, ["typed turn", "spoken turn"])
        self.assertEqual([m["role"] for m in chat["messages"]], ["user", "assistant", "user", "assistant"])
        self.assertEqual(chat["messages"][2]["input_mode"], "voice")
        self.assertEqual(len(persist_calls), 2)

    def test_voice_event_id_is_idempotent(self):
        seen = []
        self.assertTrue(claim_voice_event("event-1", seen))
        self.assertFalse(claim_voice_event("event-1", seen))
        self.assertTrue(claim_voice_event("event-2", seen))

    def test_empty_question_is_rejected_without_writing(self):
        chat = {"id": "c", "title": "New chat", "messages": []}
        with self.assertRaises(ValueError):
            process_turn(chat, "  ", answer=lambda *_: ("", []), persist=lambda _: None)
        self.assertEqual(chat["messages"], [])

    def test_context_sources_remain_on_assistant_turn(self):
        chat = {"id": "c", "title": "New chat", "messages": []}
        process_turn(chat, "find facts", answer=lambda *_: ("answer", ["https://example.com"]),
                     persist=lambda _: None)
        self.assertEqual(chat["messages"][-1]["sources"], ["https://example.com"])


if __name__ == "__main__":
    unittest.main()
