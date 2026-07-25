"""Unit tests for the 2026-07-25 addition: OpenRouter as a supplemental
provider for the "gpt"/"opensource" slots, tried only after SambaNova
returns a transient (rate-limit/5xx) error - see run_experiments.py's
OPENROUTER_MODEL_ID comment for the real-call verification and cost
numbers behind this.

Mocks _openai_compatible_call directly (the shared low-level HTTP call both
SambaNova and OpenRouter go through) rather than the openai SDK itself, so
these tests don't depend on network access or a real API key - same pattern
as test_retry.py's plain local exception classes.

Run: python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import run_experiments as rx  # noqa: E402


class _StatusCodeError(Exception):
    def __init__(self, status_code, message="fake status error"):
        super().__init__(message)
        self.status_code = status_code


class TestOpenRouterModelIdMapping(unittest.TestCase):
    def test_maps_exactly_the_two_sambanova_model_names_in_use(self):
        self.assertEqual(
            rx.OPENROUTER_MODEL_ID,
            {
                "gpt-oss-120b": "openai/gpt-oss-120b",
                "Meta-Llama-3.3-70B-Instruct": "meta-llama/llama-3.3-70b-instruct",
            },
        )


class TestCallGptOpenRouterFallback(unittest.TestCase):
    def test_sambanova_success_never_calls_openrouter(self):
        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "sk-sb", "OPENROUTER_API_KEY": "sk-or"}), \
             mock.patch.object(rx, "_openai_compatible_call", return_value=("real content", True)) as mocked:
            text, applied = rx.call_gpt("prompt", "gpt-oss-120b", 0.1, 4096)
        self.assertEqual(text, "real content")
        self.assertTrue(applied)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args[0][0], rx.SAMBANOVA_BASE_URL)

    def test_sambanova_rate_limit_falls_back_to_openrouter_and_succeeds(self):
        calls = []

        def fake(base_url, api_key, model_version, prompt, temperature, max_tokens):
            calls.append(base_url)
            if base_url == rx.SAMBANOVA_BASE_URL:
                raise _StatusCodeError(429, "SambaNova daily cap exhausted")
            return ("openrouter content", True)

        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "sk-sb", "OPENROUTER_API_KEY": "sk-or"}), \
             mock.patch.object(rx, "_openai_compatible_call", side_effect=fake):
            text, applied = rx.call_gpt("prompt", "gpt-oss-120b", 0.1, 4096)

        self.assertEqual(text, "openrouter content")
        self.assertTrue(applied)
        self.assertEqual(calls, [rx.SAMBANOVA_BASE_URL, rx.OPENROUTER_BASE_URL])

    def test_sambanova_auth_error_does_not_fall_back(self):
        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "sk-sb", "OPENROUTER_API_KEY": "sk-or"}), \
             mock.patch.object(rx, "_openai_compatible_call", side_effect=_StatusCodeError(401, "bad key")) as mocked:
            with self.assertRaises(_StatusCodeError) as ctx:
                rx.call_gpt("prompt", "gpt-oss-120b", 0.1, 4096)
        self.assertEqual(ctx.exception.status_code, 401)
        mocked.assert_called_once()  # OpenRouter never attempted

    def test_rate_limit_without_openrouter_key_raises_original_error(self):
        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "sk-sb"}, clear=False), \
             mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OPENROUTER_API_KEY", None)
            with mock.patch.object(rx, "_openai_compatible_call", side_effect=_StatusCodeError(429, "quota")) as mocked:
                with self.assertRaises(_StatusCodeError):
                    rx.call_gpt("prompt", "gpt-oss-120b", 0.1, 4096)
        mocked.assert_called_once()

    def test_rate_limit_with_unmapped_model_version_raises_original_error(self):
        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "sk-sb", "OPENROUTER_API_KEY": "sk-or"}), \
             mock.patch.object(rx, "_openai_compatible_call", side_effect=_StatusCodeError(429, "quota")) as mocked:
            with self.assertRaises(_StatusCodeError):
                rx.call_gpt("prompt", "not-a-mapped-model-version", 0.1, 4096)
        mocked.assert_called_once()


class TestCallOpensourceOpenRouterFallback(unittest.TestCase):
    def test_sambanova_rate_limit_falls_back_to_openrouter_and_succeeds(self):
        calls = []

        def fake(base_url, api_key, model_version, prompt, temperature, max_tokens):
            calls.append((base_url, model_version))
            if base_url == rx.SAMBANOVA_BASE_URL:
                raise _StatusCodeError(429, "SambaNova daily cap exhausted")
            return ("openrouter llama content", True)

        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "sk-sb", "OPENROUTER_API_KEY": "sk-or"}), \
             mock.patch.object(rx, "_openai_compatible_call", side_effect=fake):
            text, applied = rx.call_opensource("prompt", "Meta-Llama-3.3-70B-Instruct", 0.1, 4096)

        self.assertEqual(text, "openrouter llama content")
        self.assertTrue(applied)
        self.assertEqual(
            calls,
            [
                (rx.SAMBANOVA_BASE_URL, "Meta-Llama-3.3-70B-Instruct"),
                (rx.OPENROUTER_BASE_URL, "meta-llama/llama-3.3-70b-instruct"),
            ],
        )

    def test_sambanova_success_never_calls_openrouter(self):
        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "sk-sb", "OPENROUTER_API_KEY": "sk-or"}), \
             mock.patch.object(rx, "_openai_compatible_call", return_value=("real content", True)) as mocked:
            text, applied = rx.call_opensource("prompt", "Meta-Llama-3.3-70B-Instruct", 0.1, 4096)
        self.assertEqual(text, "real content")
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args[0][0], rx.SAMBANOVA_BASE_URL)


if __name__ == "__main__":
    unittest.main()
