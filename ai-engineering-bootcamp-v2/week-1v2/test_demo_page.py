"""No-network tests for Streamlit helper functions."""

import os
import unittest
from unittest.mock import patch

import demo_page


class DemoPageHelperTests(unittest.TestCase):
    @patch.dict(os.environ, {"API_BASE_URL": "https://example.test"}, clear=False)
    def test_api_base_url_uses_environment(self) -> None:
        self.assertEqual(demo_page.default_api_base_url(), "https://example.test")

    @patch.dict(os.environ, {"API_BASE_URL": ""}, clear=False)
    def test_api_base_url_defaults_to_deployed_service(self) -> None:
        self.assertEqual(
            demo_page.default_api_base_url(), demo_page.DEFAULT_DEPLOYED_API
        )

    def test_refusal_detection(self) -> None:
        self.assertTrue(
            demo_page.is_refusal_answer(
                {"answer": {"answer": demo_page.REFUSAL_ANSWER, "citations": []}}
            )
        )
        self.assertFalse(
            demo_page.is_refusal_answer(
                {"answer": {"answer": "Tuesday and Thursday only.", "citations": []}}
            )
        )

    @patch.dict(os.environ, {"INGEST_API_KEY": ""}, clear=False)
    def test_missing_ingest_key_is_empty(self) -> None:
        with patch.object(demo_page.st, "secrets") as secrets:
            secrets.get.side_effect = Exception("no secrets file")
            self.assertEqual(demo_page.get_ingest_api_key(), "")

    @patch.dict(os.environ, {"INGEST_API_KEY": "local-secret"}, clear=False)
    def test_ingest_key_comes_from_environment(self) -> None:
        self.assertEqual(demo_page.get_ingest_api_key(), "local-secret")

    def test_ask_payload_preserves_session_1_fields(self) -> None:
        payload = demo_page.build_payload("What is RAG?", "gpt-4o-mini", False)
        self.assertEqual(
            payload,
            {"question": "What is RAG?", "model": "gpt-4o-mini", "force_bad": False},
        )


if __name__ == "__main__":
    unittest.main()
