"""Guards .env.example against drifting from what the code actually reads.

Verified once by hand 2026-07-21: every env-var-shaped literal referenced in
src/ (ANTHROPIC_API_KEY, CLAUDE_MODEL_NAME, etc.) is declared in .env.example,
and vice versa - no gap, no stale entry. This file turns that into a permanent
check so a new `_require_env("SOME_NEW_KEY")` added later doesn't silently
leave whoever fills in .env without knowing it's needed (they'd only find out
at the point of a RuntimeError, potentially mid-grid), and so a renamed/removed
var doesn't leave a dead, confusing entry in .env.example.

Run: python -m unittest discover -s tests
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
ENV_EXAMPLE = REPO / ".env.example"

# Suffixes that mark a string literal as env-var-shaped (as opposed to some
# other all-caps constant, e.g. a regex name or a category label).
ENV_VAR_SUFFIXES = ("_KEY", "_TOKEN", "_NAME", "_URL", "_LABEL", "_MTOK", "_WINDOW")


def _code_referenced_vars() -> set[str]:
    literals = set()
    for f in SRC.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        literals |= set(re.findall(r'"([A-Z][A-Z0-9_]+)"', text))
        literals |= set(re.findall(r"'([A-Z][A-Z0-9_]+)'", text))
    return {v for v in literals if v.endswith(ENV_VAR_SUFFIXES)}


def _declared_vars() -> set[str]:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]+)=", text, re.MULTILINE))


class TestEnvExampleMatchesCode(unittest.TestCase):
    def test_every_code_referenced_var_is_declared(self):
        missing = sorted(_code_referenced_vars() - _declared_vars())
        self.assertEqual(
            missing, [],
            f".env.example is missing: {missing} - add them so filling in .env "
            f"doesn't require reading source to discover what's needed."
        )

    def test_no_stale_declared_var(self):
        unused = sorted(_declared_vars() - _code_referenced_vars())
        self.assertEqual(
            unused, [],
            f".env.example declares vars no longer referenced anywhere in src/: "
            f"{unused} - either the code lost a reference (check for a typo/rename) "
            f"or the entry is stale and should be removed."
        )

    def test_env_example_has_no_real_looking_secret_values(self):
        # A cheap sanity check against someone accidentally committing a real
        # key into the template file - real API keys have recognizable prefixes.
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        suspicious_prefixes = ("sk-ant-api03-", "sk-proj-", "sk-live-")
        hits = [p for p in suspicious_prefixes if p in text]
        self.assertEqual(hits, [], f".env.example contains what looks like a real key prefix: {hits}")


if __name__ == "__main__":
    unittest.main()
