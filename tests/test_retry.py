"""Unit tests for run_experiments.py's F4 addition: retry/backoff for
transient provider errors. Before this, a single flaky timeout/rate-limit/5xx
anywhere in a 189-378-cell grid needed a human to notice run_one()'s printed
FAILED line and manually re-run that one cell by hand.

_is_transient_provider_error is duck-typed (status_code attribute, or class
name matching) rather than importing anthropic/openai, so these tests use
plain local exception classes shaped the same way real SDK exceptions are
(status_code attribute for HTTP-backed errors; class name alone for
connection/timeout errors that never got an HTTP response) - this also means
these tests don't depend on anthropic/openai being installed at all.

time.sleep is stubbed throughout via mock.patch.object(rx.time, "sleep", ...)
so no test actually waits out a real backoff delay.

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
    """Shaped like anthropic.APIStatusError/openai.APIStatusError and their
    subclasses (RateLimitError, InternalServerError, BadRequestError,
    AuthenticationError, etc.) - all of which carry a numeric status_code."""

    def __init__(self, status_code, message="fake status error"):
        super().__init__(message)
        self.status_code = status_code


def _named(class_name, message="fake"):
    """A one-off exception instance whose CLASS NAME matches one of the
    markers _is_transient_provider_error checks by name - simulates
    anthropic.APIConnectionError / APITimeoutError, neither of which carries
    a status_code (there was no HTTP response to read one from)."""
    cls = type(class_name, (Exception,), {})
    return cls(message)


class TestIsTransientProviderError(unittest.TestCase):
    def test_429_rate_limit_is_transient(self):
        self.assertTrue(rx._is_transient_provider_error(_StatusCodeError(429)))

    def test_500_and_503_server_errors_are_transient(self):
        self.assertTrue(rx._is_transient_provider_error(_StatusCodeError(500)))
        self.assertTrue(rx._is_transient_provider_error(_StatusCodeError(503)))

    def test_400_bad_request_is_not_transient(self):
        self.assertFalse(rx._is_transient_provider_error(_StatusCodeError(400)))

    def test_401_auth_and_403_permission_are_not_transient(self):
        self.assertFalse(rx._is_transient_provider_error(_StatusCodeError(401)))
        self.assertFalse(rx._is_transient_provider_error(_StatusCodeError(403)))

    def test_404_not_found_is_not_transient(self):
        self.assertFalse(rx._is_transient_provider_error(_StatusCodeError(404)))

    def test_rate_limit_error_by_class_name_alone_is_transient(self):
        self.assertTrue(rx._is_transient_provider_error(_named("RateLimitError")))

    def test_internal_server_error_by_class_name_alone_is_transient(self):
        self.assertTrue(rx._is_transient_provider_error(_named("InternalServerError")))

    def test_api_connection_error_by_class_name_alone_is_transient(self):
        # The real anthropic/openai APIConnectionError carries no status_code
        # at all - there was no HTTP response to read one from.
        self.assertTrue(rx._is_transient_provider_error(_named("APIConnectionError")))

    def test_api_timeout_error_by_class_name_alone_is_transient(self):
        self.assertTrue(rx._is_transient_provider_error(_named("APITimeoutError")))

    def test_builtin_connection_error_is_transient(self):
        self.assertTrue(rx._is_transient_provider_error(ConnectionError("connection reset")))

    def test_builtin_timeout_error_is_transient(self):
        self.assertTrue(rx._is_transient_provider_error(TimeoutError("timed out")))

    def test_plain_runtime_error_is_not_transient(self):
        # This is exactly the shape _require_env raises for a missing .env
        # key - retrying it would just waste 3 attempts on something that
        # cannot ever succeed without a human filling in .env.
        self.assertFalse(rx._is_transient_provider_error(RuntimeError("ANTHROPIC_API_KEY is not set")))

    def test_plain_value_error_is_not_transient(self):
        self.assertFalse(rx._is_transient_provider_error(ValueError("some unrelated bug")))

    def test_generic_exception_with_unrecognized_name_is_not_transient(self):
        self.assertFalse(rx._is_transient_provider_error(_named("SomeUnrelatedError")))


class TestCallModelWithRetry(unittest.TestCase):
    def test_succeeds_on_first_attempt_no_sleep_no_retry(self):
        calls = []

        def fake(prompt, model_version, temperature, max_tokens):
            calls.append(1)
            return "ok", True

        with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake}), \
             mock.patch.object(rx.time, "sleep") as mock_sleep:
            result = rx._call_model_with_retry("claude", "prompt", "v1", 0.1, 100)
        self.assertEqual(result, ("ok", True))
        self.assertEqual(len(calls), 1)
        mock_sleep.assert_not_called()

    def test_fails_once_transiently_then_succeeds(self):
        calls = []

        def fake(prompt, model_version, temperature, max_tokens):
            calls.append(1)
            if len(calls) == 1:
                raise _StatusCodeError(429, "rate limited")
            return "ok", True

        with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake}), \
             mock.patch.object(rx.time, "sleep") as mock_sleep:
            result = rx._call_model_with_retry("claude", "prompt", "v1", 0.1, 100)
        self.assertEqual(result, ("ok", True))
        self.assertEqual(len(calls), 2)
        mock_sleep.assert_called_once_with(rx.RETRY_BASE_DELAY_SECONDS)  # 1.0 * 2**0

    def test_exhausts_all_attempts_then_reraises_the_original_exception(self):
        calls = []
        original = _StatusCodeError(503, "still down")

        def fake(prompt, model_version, temperature, max_tokens):
            calls.append(1)
            raise original

        with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake}), \
             mock.patch.object(rx.time, "sleep") as mock_sleep:
            with self.assertRaises(_StatusCodeError) as cm:
                rx._call_model_with_retry("claude", "prompt", "v1", 0.1, 100)
        self.assertIs(cm.exception, original)   # the ORIGINAL exception, not a wrapper
        self.assertEqual(len(calls), rx.RETRY_MAX_ATTEMPTS)
        self.assertEqual(mock_sleep.call_count, rx.RETRY_MAX_ATTEMPTS - 1)

    def test_backoff_delay_is_exponential(self):
        def fake(prompt, model_version, temperature, max_tokens):
            raise _StatusCodeError(500, "down")

        with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake}), \
             mock.patch.object(rx.time, "sleep") as mock_sleep:
            with self.assertRaises(_StatusCodeError):
                rx._call_model_with_retry("claude", "prompt", "v1", 0.1, 100)
        expected = [rx.RETRY_BASE_DELAY_SECONDS * (2 ** i) for i in range(rx.RETRY_MAX_ATTEMPTS - 1)]
        actual = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertEqual(actual, expected)

    def test_non_transient_error_is_not_retried_at_all(self):
        calls = []

        def fake(prompt, model_version, temperature, max_tokens):
            calls.append(1)
            raise _StatusCodeError(401, "bad api key")

        with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake}), \
             mock.patch.object(rx.time, "sleep") as mock_sleep:
            with self.assertRaises(_StatusCodeError):
                rx._call_model_with_retry("claude", "prompt", "v1", 0.1, 100)
        self.assertEqual(len(calls), 1)   # NOT retried
        mock_sleep.assert_not_called()

    def test_missing_env_key_runtime_error_is_not_retried(self):
        # The exact shape _require_env raises - confirms this integrates
        # correctly with the existing missing-.env-key error path, not just
        # a synthetic status-code exception.
        calls = []

        def fake(prompt, model_version, temperature, max_tokens):
            calls.append(1)
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env.")

        with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake}), \
             mock.patch.object(rx.time, "sleep") as mock_sleep:
            with self.assertRaises(RuntimeError):
                rx._call_model_with_retry("claude", "prompt", "v1", 0.1, 100)
        self.assertEqual(len(calls), 1)
        mock_sleep.assert_not_called()

    def test_transient_then_non_transient_stops_immediately_on_the_second(self):
        calls = []

        def fake(prompt, model_version, temperature, max_tokens):
            calls.append(1)
            if len(calls) == 1:
                raise _StatusCodeError(429, "rate limited")
            raise _StatusCodeError(400, "now a real bad request")

        with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake}), \
             mock.patch.object(rx.time, "sleep") as mock_sleep:
            with self.assertRaises(_StatusCodeError) as cm:
                rx._call_model_with_retry("claude", "prompt", "v1", 0.1, 100)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(len(calls), 2)
        mock_sleep.assert_called_once()   # only the first (transient) failure slept


class TestRunOneUsesTheRetryWrapper(unittest.TestCase):
    """Integration-level proof that run_one() actually goes through
    _call_model_with_retry rather than calling MODEL_DISPATCH[label]
    directly - the unit tests above would all pass vacuously if run_one()
    had never been wired up to use the wrapper at all."""

    def test_run_one_recovers_from_one_transient_failure(self):
        import tempfile

        calls = []

        def flaky(prompt, model_version, temperature, max_tokens):
            calls.append(1)
            if len(calls) == 1:
                raise _StatusCodeError(503, "temporarily down")
            return '{"project_id": "' + rx.all_project_ids()[0] + '", "risks": []}', True

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "results").mkdir()
            with mock.patch.object(rx, "REPO_ROOT", root), \
                 mock.patch.object(rx, "RAW_OUTPUTS_DIR", root / "results" / "raw_outputs"), \
                 mock.patch.object(rx, "RUN_CONFIG_LOG", root / "results" / "run_config.jsonl"), \
                 mock.patch.object(rx, "BATCH_JOBS_LOG", root / "results" / "batch_jobs.json"), \
                 mock.patch.dict("os.environ", {"CLAUDE_MODEL_NAME": "claude-sonnet-5"}), \
                 mock.patch.dict(rx.MODEL_DISPATCH, {"claude": flaky}), \
                 mock.patch.object(rx.time, "sleep") as mock_sleep:
                project_id = rx.all_project_ids()[0]
                out_path = rx.run_one(project_id, "claude", "zero_shot", 1, 0.1, 100)
        self.assertTrue(out_path.name.endswith(".json"))
        self.assertEqual(len(calls), 2)
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
