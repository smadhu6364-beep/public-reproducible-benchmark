"""Regression tests for the `_show()` out-of-repo-path crash class.

This exact bug - a script's final status print calling
`out_path.relative_to(REPO_ROOT)` unconditionally, which raises ValueError if
the caller pointed --out-dir/--report outside the repo (a normal, legal thing
to do - e.g. rendering synthetic figures into scratch/, as
docs/run_playbook.md itself documents) - has now been found and fixed FIVE
separate times in this repo: build_rater_packets.py, make_figures.py,
judge.py, match.py, and validate_threshold.py. Each fix uses the same `_show()`
helper (try relative_to(REPO_ROOT), fall back to the resolved absolute path).

Two things pinned here:
1. Each module's `_show()` behaves correctly on both an inside-repo and an
   outside-repo path.
2. A static sweep across src/ and analysis/ so a SIXTH occurrence of the bare
   `.relative_to(REPO_ROOT)` pattern - reintroduced in a new or existing
   script without going through `_show()` - fails a test immediately instead
   of waiting to be found by hand again.

Run: python -m unittest discover -s tests
"""

import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPO / "analysis"))

import match          # noqa: E402
import judge           # noqa: E402
import validate_threshold  # noqa: E402
import build_rater_packets  # noqa: E402

MODULES_WITH_SHOW = [match, judge, validate_threshold, build_rater_packets]

try:
    import make_figures  # noqa: E402
    MODULES_WITH_SHOW.append(make_figures)
except ImportError:
    # matplotlib not installed in this interpreter - same situation as
    # test_figures.py. The module-object tests below simply cover one fewer
    # module in that case; the static text-sweep test still scans
    # make_figures.py's SOURCE regardless (it reads files as text, it never
    # imports them), so that coverage isn't lost either way.
    pass


class TestShowHelperOnEveryFixedModule(unittest.TestCase):
    def test_every_module_exposes_a_show_function(self):
        for mod in MODULES_WITH_SHOW:
            with self.subTest(module=mod.__name__):
                self.assertTrue(hasattr(mod, "_show"), f"{mod.__name__} has no _show()")
                self.assertTrue(callable(mod._show))

    def test_inside_repo_path_returns_relative_string(self):
        for mod in MODULES_WITH_SHOW:
            with self.subTest(module=mod.__name__):
                shown = mod._show(REPO / "results" / "example.json")
                self.assertFalse(Path(shown).is_absolute())

    def test_outside_repo_path_does_not_raise(self):
        # THE regression: this used to be `path.relative_to(REPO_ROOT)` with no
        # fallback, raising ValueError for exactly this input.
        with tempfile.TemporaryDirectory() as td:
            outside = Path(td) / "somewhere" / "report.md"
            for mod in MODULES_WITH_SHOW:
                with self.subTest(module=mod.__name__):
                    shown = mod._show(outside)   # must not raise
                    self.assertTrue(Path(shown).is_absolute())

    def test_relative_input_path_is_resolved_not_raised(self):
        for mod in MODULES_WITH_SHOW:
            with self.subTest(module=mod.__name__):
                self.assertIsInstance(mod._show(Path("results/example.json")), str)


class TestNoUnguardedRelativeToRepoRoot(unittest.TestCase):
    """Static sweep: every `.relative_to(REPO_ROOT)` (or `.relative_to(rx.REPO_ROOT)`
    etc.) call in src/ or analysis/ must be reached only through a `_show()`
    function, or be one of the explicitly-verified-safe sites below, never bare
    in a print/f-string that a user-supplied path could reach."""

    PATTERN = re.compile(r"\.relative_to\(\s*\w*REPO_ROOT\s*\)")

    # Manually verified 2026-07-21: each of these is a FIXED module-level
    # constant (RAW_OUTPUTS_DIR, BATCH_JOBS_LOG, PILOT_PATH), confirmed via
    # `grep add_argument` to have no corresponding CLI flag anywhere that could
    # point it outside REPO_ROOT - unlike --out-dir/--report, which are exactly
    # that kind of user-supplied override and are the actual bug class this
    # test guards against. Safe by construction, not by luck: every test that
    # patches one of these constants (_SandboxedRun, _SandboxedBatch) patches
    # REPO_ROOT to the same temp root in the same context manager, so the two
    # never drift apart even under test. Listed explicitly, with line numbers,
    # so an edit that moves the code doesn't silently keep the allowlist valid
    # for the wrong line.
    ALLOWED = {
        # Shifted 2026-07-23 by run_experiments.py's new _load_env() (added
        # for the .env-not-actually-loaded fix) - same constants, same
        # justification, just further down the file.
        ("run_experiments.py", 752),   # raw_output_path -> fixed RAW_OUTPUTS_DIR, no CLI override
        ("run_experiments.py", 976),   # BATCH_JOBS_LOG -> fixed constant, no CLI override
        ("run_experiments.py", 1079),  # BATCH_JOBS_LOG -> fixed constant, no CLI override
        ("run_experiments.py", 1266),  # raw_output_path -> fixed RAW_OUTPUTS_DIR, no CLI override
        ("validate_threshold.py", 191),  # PILOT_PATH -> fixed constant, no CLI override
    }

    def test_no_bare_relative_to_repo_root_outside_a_show_function_or_the_allowlist(self):
        offenders = []
        stale_allowlist_entries = set(self.ALLOWED)
        for py_file in list(SRC.glob("*.py")) + list((REPO / "analysis").glob("*.py")):
            text = py_file.read_text(encoding="utf-8")
            lines = text.splitlines()
            in_show_def = False
            show_indent = None
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("def _show("):
                    in_show_def = True
                    show_indent = len(line) - len(line.lstrip())
                    continue
                if in_show_def:
                    # Left the _show() body once we hit a line at or below its
                    # own indent that starts a new statement (blank lines don't count).
                    if stripped and (len(line) - len(line.lstrip())) <= show_indent:
                        in_show_def = False
                if in_show_def:
                    continue
                if self.PATTERN.search(line):
                    key = (py_file.name, i)
                    if key in self.ALLOWED:
                        stale_allowlist_entries.discard(key)
                        continue
                    offenders.append(f"{py_file.relative_to(REPO)}:{i}: {stripped}")
        self.assertEqual(
            offenders, [],
            "Found .relative_to(REPO_ROOT) outside a _show() helper and not in the "
            "verified-safe ALLOWED set above - this is the exact crash class fixed "
            "5 times already (out-of-repo --out-dir/--report raises ValueError after "
            "the real work already succeeded). If this path is derived from a CLI "
            "flag, route it through a _show() helper. If it's a genuinely fixed, "
            "non-configurable constant like the ones already allowlisted, verify "
            "that with `grep add_argument` and add it to ALLOWED with the same "
            "justification:\n" + "\n".join(offenders)
        )
        self.assertEqual(
            stale_allowlist_entries, set(),
            f"ALLOWED entries that no longer match any line (file moved/edited, "
            f"update the line numbers): {stale_allowlist_entries}"
        )


if __name__ == "__main__":
    unittest.main()
