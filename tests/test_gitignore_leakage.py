"""Guards the git-level half of the leakage rule: the directories/files that
must never be committed stay gitignored, and the ones that must ship with the
repo stay tracked. Complements audit_corpus.py's content-level leakage checks
(is the register text actually excised) with a structural check (is the
container for sensitive material even reachable from a commit).

Uses `git check-ignore` / `git ls-files` directly - the actual mechanism git
uses, not a hand-parsed .gitignore, so this can't drift from what git really
does.

Run: python -m unittest discover -s tests
"""

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _is_ignored(relpath: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", relpath], cwd=REPO,
    )
    return result.returncode == 0


def _tracked_files(relpath: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", relpath], cwd=REPO, capture_output=True, text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


@unittest.skipUnless((REPO / ".git").exists(), "requires a real git repository")
class TestLeakageSensitivePathsAreIgnored(unittest.TestCase):
    def test_data_raw_is_ignored(self):
        self.assertTrue(_is_ignored("data/raw/example.pdf"),
                        "data/raw/ (source PDFs, may contain the register in-line) must be gitignored")

    def test_risk_source_audit_is_ignored(self):
        self.assertTrue(_is_ignored("data/risk_source_audit/example.txt"),
                        "data/risk_source_audit/ (excised register text, audit-only) must be gitignored")

    def test_env_file_is_ignored(self):
        self.assertTrue(_is_ignored(".env"), ".env (API keys) must be gitignored")

    def test_blinding_map_is_ignored(self):
        self.assertTrue(
            _is_ignored("results/rater_packets/blinding_map.csv"),
            "the Method B de-anonymizing key must be gitignored - see docs/rater_protocol.md",
        )

    def test_no_leakage_sensitive_file_is_actually_tracked(self):
        # The stronger check: not just "gitignore has a rule" but "nothing
        # currently in the index actually violates it" - a file added with
        # `git add -f` before the ignore rule existed would slip past the
        # ignore check alone.
        for path in ("data/risk_source_audit", "data/raw"):
            tracked = [f for f in _tracked_files(path) if not f.endswith(".gitkeep")]
            self.assertEqual(tracked, [], f"{path} has tracked, non-.gitkeep files: {tracked}")


@unittest.skipUnless((REPO / ".git").exists(), "requires a real git repository")
class TestCorpusTextIsTracked(unittest.TestCase):
    """The inverse failure mode: if data/processed/ were accidentally
    gitignored, the safe planning text wouldn't ship with the repo at all and
    the pipeline would look broken to anyone who clones fresh."""

    def test_processed_planning_text_is_not_ignored(self):
        self.assertFalse(_is_ignored("data/processed/example.txt"))

    def test_ground_truth_registers_are_not_ignored(self):
        self.assertFalse(_is_ignored("data/ground_truth/example.json"))

    def test_processed_directory_has_tracked_content(self):
        tracked = _tracked_files("data/processed")
        self.assertGreater(len(tracked), 1, "data/processed/ should ship real corpus text, not just .gitkeep")


if __name__ == "__main__":
    unittest.main()
