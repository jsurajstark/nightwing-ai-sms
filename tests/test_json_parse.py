"""Tests for LLM JSON parsing helpers."""

from __future__ import annotations

import unittest

from sms_demo.llm.base import LLMError
from sms_demo.llm.json_parse import parse_llm_json


class ParseLlmJsonTest(unittest.TestCase):
    def test_parses_plain_object(self) -> None:
        parsed = parse_llm_json('{"patient_first_name": "Lily", "patient_last_name": "Chen"}')
        self.assertEqual(parsed["patient_first_name"], "Lily")
        self.assertEqual(parsed["patient_last_name"], "Chen")

    def test_strips_markdown_fence(self) -> None:
        parsed = parse_llm_json(
            '```json\n{"patient_first_name": "Lily", "confidence": 0.9}\n```'
        )
        self.assertEqual(parsed["patient_first_name"], "Lily")

    def test_extracts_object_from_wrapped_text(self) -> None:
        parsed = parse_llm_json('Here is the JSON:\n{"patient_first_name": "Ana"}\nDone.')
        self.assertEqual(parsed["patient_first_name"], "Ana")

    def test_invalid_json_is_retryable(self) -> None:
        with self.assertRaises(LLMError) as ctx:
            parse_llm_json('{"patient_first_name": "Lily", "patient_last_name')
        self.assertTrue(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
