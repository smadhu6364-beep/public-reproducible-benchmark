"""Unit tests for src/check_env.py - the pre-run connectivity check.

REDESIGNED 2026-07-23 alongside check_env.py's own free-tier rewrite (see
that file's module docstring): all 3 slots now go through the same
OpenAI-compatible-endpoint check (_check_openai_compatible_endpoint), so this
file tests that shared function once, then exercises each of the 3 thin
per-slot wrappers (check_claude_slot/check_gpt_slot/check_opensource_slot)
for correct labeling, env-var name, and base URL - not the whole check logic
three separate times.

check_env.py's whole job is to be trustworthy BEFORE the real grid runs, so
its own failure modes matter: does it correctly report "not configured"
without making a network call (no key = no call, ever), does a real auth
failure surface as FAIL rather than crashing the whole check, and does
main()'s exit code correctly distinguish "nothing configured" (0, fine, keys
just aren't filled in yet) from "something configured but broken" (1, a real
problem worth stopping for).

All network calls are mocked via urllib.request.urlopen - no real network,
no real keys.

Run: python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import check_env as ce  # noqa: E402


class _FakeHTTPResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(should_raise=None, status=200):
    calls = []

    def fake(req, timeout=None):
        calls.append(req)
        if should_raise:
            raise should_raise
        return _FakeHTTPResponse(status)

    return fake, calls


class TestCheckOpenAICompatibleEndpointShared(unittest.TestCase):
    """The one real check function all 3 slots delegate to."""

    def test_ok_when_the_call_succeeds(self):
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce._check_openai_compatible_endpoint(
                "Test Label", "https://example.com/v1", "fake-key")
        self.assertTrue(configured)
        self.assertEqual(result, "OK")
        self.assertEqual(label, "Test Label")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].full_url, "https://example.com/v1/models")
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake-key")

    def test_sends_a_real_user_agent_not_the_urllib_default(self):
        # Found 2026-07-23: a bare urllib request (Python's default
        # User-Agent) got a 403 from something in front of a real
        # third-party OpenAI-compatible endpoint during diagnosis, while an
        # explicit header succeeded - not cosmetic, a missing one can make a
        # genuinely valid key look like a real failure.
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            ce._check_openai_compatible_endpoint("Test Label", "https://example.com/v1", "fake-key")
        user_agent = calls[0].get_header("User-agent")   # urllib title-cases header keys
        self.assertTrue(user_agent)
        self.assertNotIn("Python-urllib", user_agent)

    def test_http_error_reports_fail_not_a_crash(self):
        import urllib.error

        fake_urlopen, _ = _fake_urlopen(should_raise=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None))
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce._check_openai_compatible_endpoint(
                "Test Label", "https://example.com/v1", "bad-key")
        self.assertTrue(configured)
        self.assertTrue(result.startswith("FAIL"))
        self.assertIn("401", result)

    def test_other_exception_reports_fail_not_a_crash(self):
        fake_urlopen, _ = _fake_urlopen(should_raise=TimeoutError("timed out"))
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce._check_openai_compatible_endpoint(
                "Test Label", "https://example.com/v1", "fake-key")
        self.assertTrue(result.startswith("FAIL"))
        self.assertIn("timed out", result)

    def test_trailing_slash_in_base_url_does_not_produce_a_double_slash(self):
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            ce._check_openai_compatible_endpoint("Test Label", "https://example.com/v1/", "fake-key")
        self.assertEqual(calls[0].full_url, "https://example.com/v1/models")


class TestPerSlotWrappers(unittest.TestCase):
    """Each of the 3 real MODEL_DISPATCH slots: correct env var read, correct
    base URL, correct label, and "not configured" (no network call at all)
    when the key is missing."""

    def test_claude_slot_not_configured_when_key_missing_and_makes_no_call(self):
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_claude_slot()
        self.assertFalse(configured)
        self.assertEqual(result, "not configured")
        self.assertEqual(calls, [])

    def test_claude_slot_uses_gemini_api_key_and_base_url(self):
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "fake-gemini-key"}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_claude_slot()
        self.assertTrue(configured)
        self.assertEqual(result, "OK")
        self.assertIn("Gemini", label)
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake-gemini-key")
        self.assertTrue(calls[0].full_url.startswith(ce.GEMINI_BASE_URL))

    def test_gpt_slot_not_configured_when_key_missing_and_makes_no_call(self):
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_gpt_slot()
        self.assertFalse(configured)
        self.assertEqual(calls, [])

    def test_gpt_slot_uses_sambanova_api_key_and_base_url(self):
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "fake-sambanova-key"}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_gpt_slot()
        self.assertTrue(configured)
        self.assertEqual(result, "OK")
        self.assertIn("SambaNova", label)
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake-sambanova-key")
        self.assertTrue(calls[0].full_url.startswith(ce.SAMBANOVA_BASE_URL))

    def test_opensource_slot_not_configured_when_key_missing_and_makes_no_call(self):
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_opensource_slot()
        self.assertFalse(configured)
        self.assertEqual(calls, [])

    def test_opensource_slot_shares_sambanova_api_key_with_gpt_slot(self):
        # Both slots use the SAME SambaNova account/key, different model
        # names (the model name itself isn't part of this connectivity check).
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch.dict("os.environ", {"SAMBANOVA_API_KEY": "fake-sambanova-key"}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_opensource_slot()
        self.assertTrue(configured)
        self.assertEqual(result, "OK")
        self.assertIn("SambaNova", label)
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake-sambanova-key")
        self.assertTrue(calls[0].full_url.startswith(ce.SAMBANOVA_BASE_URL))

    def test_auth_failure_reported_not_raised(self):
        import urllib.error

        fake_urlopen, _ = _fake_urlopen(should_raise=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None))
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "bad-key"}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_claude_slot()
        self.assertTrue(configured)
        self.assertTrue(result.startswith("FAIL"))


class TestMainExitCodes(unittest.TestCase):
    def _run_main(self, env=None, urlopen_fake=None):
        fake, _ = urlopen_fake if urlopen_fake else _fake_urlopen()
        with mock.patch.dict("os.environ", env or {}, clear=True), \
             mock.patch.object(ce, "_load_env", lambda: None), \
             mock.patch("urllib.request.urlopen", fake):
            return ce.main()

    def test_nothing_configured_returns_zero(self):
        self.assertEqual(self._run_main(env={}), 0)

    def test_all_configured_and_ok_returns_zero(self):
        code = self._run_main(env={"GEMINI_API_KEY": "a", "SAMBANOVA_API_KEY": "b"})
        self.assertEqual(code, 0)

    def test_any_fail_returns_one(self):
        import urllib.error

        bad_urlopen, _ = _fake_urlopen(should_raise=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None))
        code = self._run_main(env={"GEMINI_API_KEY": "bad"}, urlopen_fake=(bad_urlopen, None))
        self.assertEqual(code, 1)

    def test_missing_env_file_prints_a_note_but_still_completes(self):
        with mock.patch.object(ce, "ENV_PATH", Path("definitely/does/not/exist/.env")):
            code = self._run_main(env={})
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
