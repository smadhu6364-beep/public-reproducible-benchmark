"""Unit tests for src/extract.py's --all driver (_iter_all_projects) and
main() CLI. test_extract.py covers the pure parsing helpers;
test_extract_excision.py covers extract_project()'s page-partition and
leakage guards directly. This file covers the layer above that: iterating
every data/raw/ subdirectory and deciding what happens when one project fails
- untested until now.

Run: python -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import extract  # noqa: E402


class TestIterAllProjects(unittest.TestCase):
    def test_no_subdirectories_warns_and_returns_without_crashing(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            raw_dir.mkdir()
            extract._iter_all_projects(raw_dir, Path(td) / "out")   # must not raise

    def test_calls_extract_project_once_per_subdirectory(self):
        calls = []

        def fake_extract_project(project_id, input_path, output_dir, risk_audit_dir, manifest_path):
            calls.append(project_id)

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            (raw_dir / "P-A").mkdir(parents=True)
            (raw_dir / "P-B").mkdir(parents=True)
            with mock.patch.object(extract, "extract_project", side_effect=fake_extract_project):
                extract._iter_all_projects(raw_dir, Path(td) / "out")
        self.assertEqual(sorted(calls), ["P-A", "P-B"])

    def test_a_files_that_is_not_a_directory_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            raw_dir.mkdir()
            (raw_dir / "not_a_project.txt").write_text("stray file", encoding="utf-8")
            (raw_dir / "P-A").mkdir()
            calls = []
            with mock.patch.object(extract, "extract_project",
                                   side_effect=lambda pid, *a, **k: calls.append(pid)):
                extract._iter_all_projects(raw_dir, Path(td) / "out")
        self.assertEqual(calls, ["P-A"])

    def test_one_project_failing_does_not_stop_the_others(self):
        # A single un-page-confirmed or leakage-guard-tripped project must not
        # abort the rest of a --all run - the whole point of catching
        # FileNotFoundError/RuntimeError per-project rather than letting one
        # bad row take down every other project's extraction.
        def flaky(project_id, *a, **k):
            if project_id == "P-BAD":
                raise extract.LeakageGuardError("no confirmed pages")
            return None

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            for pid in ("P-A", "P-BAD", "P-C"):
                (raw_dir / pid).mkdir(parents=True)
            with mock.patch.object(extract, "extract_project", side_effect=flaky):
                extract._iter_all_projects(raw_dir, Path(td) / "out")   # must not raise

    def test_unexpected_exception_type_is_not_swallowed(self):
        # Only FileNotFoundError/RuntimeError (LeakageGuardError's base) are
        # caught per-project - a genuinely unexpected error (e.g. a real bug)
        # must still surface, not be silently absorbed into "skipped".
        def boom(project_id, *a, **k):
            raise ValueError("this is not a recognized skip-and-continue error")

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            (raw_dir / "P-A").mkdir(parents=True)
            with mock.patch.object(extract, "extract_project", side_effect=boom):
                with self.assertRaises(ValueError):
                    extract._iter_all_projects(raw_dir, Path(td) / "out")


class TestMainCLI(unittest.TestCase):
    def test_all_flag_delegates_to_iter_all_projects(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            raw_dir.mkdir()
            with mock.patch.object(extract, "_iter_all_projects") as mock_iter:
                code = extract.main(["--all", "--raw-dir", str(raw_dir), "--output-dir", str(Path(td) / "out")])
        self.assertEqual(code, 0)
        mock_iter.assert_called_once()

    def test_all_flag_returns_zero_even_if_iter_all_projects_skipped_every_project(self):
        # CHARACTERIZATION, not an endorsement: _iter_all_projects only prints
        # to stderr on a per-project failure, it never tracks or returns a
        # failure count - so main()'s --all path returns 0 unconditionally,
        # even in the worst case where every single project was skipped. A
        # caller relying on this exit code to detect "did the extraction
        # actually work" cannot - only the printed "!! skipped" lines can tell
        # you that today. Pinned so a change to this is a conscious one, not
        # a side effect of an unrelated edit.
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            (raw_dir / "P-BAD").mkdir(parents=True)
            with mock.patch.object(extract, "extract_project",
                                   side_effect=extract.LeakageGuardError("no confirmed pages")):
                code = extract.main(["--all", "--raw-dir", str(raw_dir), "--output-dir", str(Path(td) / "out")])
        self.assertEqual(code, 0)

    def test_missing_required_args_without_all_is_a_usage_error(self):
        with self.assertRaises(SystemExit):
            extract.main([])

    def test_single_project_success_returns_zero(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(extract, "extract_project", return_value=Path(td) / "out.txt"):
                code = extract.main(["--project-id", "P-A", "--input", str(Path(td) / "fake.pdf"),
                                     "--output-dir", str(Path(td) / "out")])
        self.assertEqual(code, 0)

    def test_single_project_failure_returns_one_and_prints_error(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(extract, "extract_project",
                                   side_effect=extract.LeakageGuardError("no confirmed pages")):
                code = extract.main(["--project-id", "P-A", "--input", str(Path(td) / "fake.pdf"),
                                     "--output-dir", str(Path(td) / "out")])
        self.assertEqual(code, 1)

    def test_file_not_found_is_also_caught_as_exit_one(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(extract, "extract_project",
                                   side_effect=FileNotFoundError("no PDF")):
                code = extract.main(["--project-id", "P-A", "--input", str(Path(td) / "fake.pdf"),
                                     "--output-dir", str(Path(td) / "out")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
