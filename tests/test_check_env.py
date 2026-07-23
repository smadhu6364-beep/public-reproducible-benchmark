"""Unit tests for src/check_env.py - the pre-spend connectivity check.

check_env.py's whole job is to be trustworthy BEFORE the real grid runs, so
its own failure modes matter: does it correctly report "not configured"
without making a network call (no key = no call, ever), does a real auth
failure surface as FAIL rather than crashing the whole check, and does
main()'s exit code correctly distinguish "nothing configured" (0, fine, keys
just aren't filled in yet) from "something configured but broken" (1, a real
problem worth stopping for).

All provider SDKs are hand-built fakes injected via sys.modules - no network,
no real keys.

Run: python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import check_env as ce  # noqa: E402


def _fake_anthropic_module(should_raise=None):
    calls = []

    class FakeModels:
        def list(self, limit=None):
            calls.append(limit)
            if should_raise:
                raise should_raise
            return SimpleNamespace(data=[])

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.models = FakeModels()

    return SimpleNamespace(Anthropic=FakeAnthropic), calls


def _fake_openai_module(should_raise=None):
    calls = []

    class FakeModels:
        def list(self):
            calls.append(True)
            if should_raise:
                raise should_raise
            return SimpleNamespace(data=[])

    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.api_key = api_key
            self.base_url = base_url
            self.models = FakeModels()

    return SimpleNamespace(OpenAI=FakeOpenAI), calls


class _FakeHTTPResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(should_raise=None, status=200):
    """check_opensource() hits {base_url}/models directly over HTTP (not via
    the openai SDK, since Together AI's /v1/models returns a bare list that
    crashes the SDK's response parsing - see check_env.py's comment). Records
    every Request object it was called with, so tests can assert on the URL/
    headers actually sent, not just that *a* call happened."""
    calls = []

    def fake(req, timeout=None):
        calls.append(req)
        if should_raise:
            raise should_raise
        return _FakeHTTPResponse(status)

    return fake, calls


def _fake_hf_hub_module(should_raise=None, username="a-real-user"):
    class FakeHfApi:
        def whoami(self, token=None):
            if should_raise:
                raise should_raise
            return {"name": username}

    return SimpleNamespace(HfApi=FakeHfApi)


class TestCheckAnthropic(unittest.TestCase):
    def test_not_configured_when_key_missing_and_makes_no_call(self):
        fake_mod, calls = _fake_anthropic_module()
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
            os_environ_pop = None  # ensure ANTHROPIC_API_KEY truly absent
            label, configured, result = ce.check_anthropic()
        self.assertFalse(configured)
        self.assertEqual(result, "not configured")
        self.assertEqual(calls, [], "must not call the API when no key is set")

    def test_ok_when_the_call_succeeds(self):
        fake_mod, calls = _fake_anthropic_module()
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-fake"}), \
             mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
            label, configured, result = ce.check_anthropic()
        self.assertTrue(configured)
        self.assertEqual(result, "OK")
        self.assertEqual(calls, [1])   # models.list(limit=1) - cheapest possible call

    def test_configured_but_auth_fails_reports_fail_not_a_crash(self):
        fake_mod, _ = _fake_anthropic_module(should_raise=RuntimeError("401 unauthorized"))
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-bad"}), \
             mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
            label, configured, result = ce.check_anthropic()
        self.assertTrue(configured)   # a key WAS present
        self.assertTrue(result.startswith("FAIL"))
        self.assertIn("401 unauthorized", result)


class TestCheckOpenAI(unittest.TestCase):
    def test_not_configured_when_key_missing(self):
        fake_mod, calls = _fake_openai_module()
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch.dict(sys.modules, {"openai": fake_mod}):
            label, configured, result = ce.check_openai()
        self.assertFalse(configured)
        self.assertEqual(calls, [])

    def test_ok_when_the_call_succeeds(self):
        fake_mod, calls = _fake_openai_module()
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-fake"}), \
             mock.patch.dict(sys.modules, {"openai": fake_mod}):
            label, configured, result = ce.check_openai()
        self.assertTrue(configured)
        self.assertEqual(result, "OK")

    def test_auth_failure_reported_not_raised(self):
        fake_mod, _ = _fake_openai_module(should_raise=RuntimeError("invalid_api_key"))
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-bad"}), \
             mock.patch.dict(sys.modules, {"openai": fake_mod}):
            label, configured, result = ce.check_openai()
        self.assertTrue(result.startswith("FAIL"))


class TestCheckOpensource(unittest.TestCase):
    def test_not_configured_when_neither_base_url_nor_hf_token_set(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            label, configured, result = ce.check_opensource()
        self.assertFalse(configured)
        self.assertIn("neither OPENSOURCE_BASE_URL nor HF_TOKEN", result)

    def test_base_url_path_reports_ok(self):
        fake_urlopen, calls = _fake_urlopen()
        env = {"OPENSOURCE_BASE_URL": "https://api.together.xyz/v1", "OPENSOURCE_API_KEY": "fake"}
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_opensource()
        self.assertTrue(configured)
        self.assertEqual(result, "OK")
        self.assertIn("together.xyz", label)   # the base_url is surfaced for clarity
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].full_url, "https://api.together.xyz/v1/models")
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake")

    def test_base_url_path_sends_a_real_user_agent(self):
        # Found 2026-07-23 on the first real call ever made against a live
        # OPENSOURCE_BASE_URL: a bare urllib request (Python's default
        # User-Agent) got a 403 from a proxy/WAF in front of Together AI's
        # endpoint, while the openai SDK's own request (different UA)
        # succeeded - so this header isn't cosmetic, a missing/default one
        # can make a genuinely valid key look like a real failure.
        fake_urlopen, calls = _fake_urlopen()
        env = {"OPENSOURCE_BASE_URL": "https://api.together.xyz/v1", "OPENSOURCE_API_KEY": "fake"}
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            ce.check_opensource()
        user_agent = calls[0].get_header("User-agent")   # urllib title-cases header keys
        self.assertTrue(user_agent, "no explicit User-Agent was sent")
        self.assertNotIn("Python-urllib", user_agent)   # i.e. not left at the default

    def test_base_url_path_http_error_reports_fail_not_a_crash(self):
        import urllib.error

        fake_urlopen, _ = _fake_urlopen(
            should_raise=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None))
        env = {"OPENSOURCE_BASE_URL": "https://api.together.xyz/v1", "OPENSOURCE_API_KEY": "bad"}
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_opensource()
        self.assertTrue(configured)
        self.assertTrue(result.startswith("FAIL"))
        self.assertIn("401", result)

    def test_hf_token_path_reports_ok_with_username(self):
        fake_hf = _fake_hf_hub_module(username="madhu-test")
        with mock.patch.dict("os.environ", {"HF_TOKEN": "hf_fake"}, clear=True), \
             mock.patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            label, configured, result = ce.check_opensource()
        self.assertTrue(configured)
        self.assertEqual(result, "OK")
        self.assertIn("madhu-test", label)

    def test_base_url_takes_priority_when_both_are_set(self):
        # Documents the actual branch order in check_opensource(): BASE_URL is
        # checked first, so if both env vars are ever set simultaneously,
        # HF_TOKEN is silently not exercised at all - worth knowing before
        # debugging "why didn't my HF token get checked".
        fake_urlopen, calls = _fake_urlopen()
        with mock.patch.dict("os.environ", {"OPENSOURCE_BASE_URL": "https://api.together.xyz/v1",
                                            "HF_TOKEN": "hf_fake"}, clear=True), \
             mock.patch("urllib.request.urlopen", fake_urlopen):
            label, configured, result = ce.check_opensource()
        self.assertIn("self-hosted endpoint", label)
        self.assertEqual(len(calls), 1)   # the HTTP path was used, not HF

    def test_hf_hub_not_installed_is_reported_not_a_crash(self):
        with mock.patch.dict("os.environ", {"HF_TOKEN": "hf_fake"}, clear=True), \
             mock.patch.dict(sys.modules, {"huggingface_hub": None}):
            label, configured, result = ce.check_opensource()
        self.assertTrue(configured)
        self.assertTrue(result.startswith("FAIL"))
        self.assertIn("not installed", result)


class TestMainExitCodes(unittest.TestCase):
    def _run_main(self, anthropic_mod=None, openai_mod=None, env=None):
        modules = {}
        if anthropic_mod:
            modules["anthropic"] = anthropic_mod
        if openai_mod:
            modules["openai"] = openai_mod
        with mock.patch.dict("os.environ", env or {}, clear=True), \
             mock.patch.object(ce, "_load_env", lambda: None), \
             mock.patch.dict(sys.modules, modules):
            return ce.main()

    def test_nothing_configured_returns_zero(self):
        self.assertEqual(self._run_main(env={}), 0)

    def test_all_configured_and_ok_returns_zero(self):
        anthropic_mod, _ = _fake_anthropic_module()
        openai_mod, _ = _fake_openai_module()
        code = self._run_main(anthropic_mod, openai_mod,
                              {"ANTHROPIC_API_KEY": "sk-a", "OPENAI_API_KEY": "sk-b"})
        self.assertEqual(code, 0)

    def test_any_fail_returns_one(self):
        anthropic_mod, _ = _fake_anthropic_module(should_raise=RuntimeError("boom"))
        code = self._run_main(anthropic_mod, None, {"ANTHROPIC_API_KEY": "sk-bad"})
        self.assertEqual(code, 1)

    def test_missing_env_file_prints_a_note_but_still_completes(self):
        with mock.patch.object(ce, "ENV_PATH", Path("definitely/does/not/exist/.env")):
            code = self._run_main(env={})
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
