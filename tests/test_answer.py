import json
import unittest
from unittest.mock import patch

from open_router.client import OpenRouterError
from open_router.luna.answer import Source, answer_from_sources


class AnswerTest(unittest.TestCase):
    source = Source("snapshot-1", "b2", "https://example.test/price", "$19", ("Harbor",))

    @patch("open_router.luna.answer.request_chat")
    def test_extract_copies_original_text(self, chat):
        chat.return_value = self.response(True, "19 dollars", ["s1"])
        answer = answer_from_sources("Give the exact price.", (self.source,), "extract")
        self.assertEqual(answer.text, "$19")
        self.assertEqual(answer.sources, (self.source,))
        chat.assert_called_once()

    @patch("open_router.luna.answer.request_chat")
    def test_unknown_source_is_rejected(self, chat):
        chat.return_value = self.response(True, "$19", ["s2"])
        with self.assertRaises(OpenRouterError):
            answer_from_sources("What is the price?", (self.source,), "summary")

    @patch("open_router.luna.answer.request_chat")
    def test_missing_evidence(self, chat):
        chat.return_value = self.response(False, "No departure time was provided.", [])
        answer = answer_from_sources("When does it depart?", (self.source,), "summary")
        self.assertFalse(answer.supported)

    @staticmethod
    def response(supported, text, ids):
        content = json.dumps({"supported": supported, "text": text, "ids": ids})
        return {"choices": [{"message": {"content": content}}]}
