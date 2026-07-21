"""Unit tests for src/metrics.py's main() CLI - previously zero coverage
(confirmed by grep: no class Test.*CLI/Main anywhere in test_metrics.py, no
direct metrics.main( call anywhere in the suite). test_metrics.py already
covers the arithmetic (run_metrics, compute_all's aggregation); this file
covers the layer above that: --scored-dir/--out argument handling, that --out
actually writes a file (vs. stdout-only when omitted), what stdout gets vs.
what the file gets, and the missing/empty-directory exit path.

No stubbing needed - compute_all() only ever reads whatever *.match.json
files are on disk under the directory it's given, so pointing --scored-dir
at a real temp directory with real fixture files is simpler and more direct
than mocking.

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import metrics  # noqa: E402


def _write_match_file(dir_path: Path, name: str, *, project_id="P-TEST", model="claude",
                       prompt="zero_shot", run_index=1, parse_failed=False):
    match_result = {
        "project_id": project_id, "model": model, "prompt_strategy": prompt,
        "run_index": run_index, "parse_failed": parse_failed,
        "gen_risks": [] if parse_failed else [{"risk_id": "R01", "category": "schedule"}],
        "gt_risks": [{"risk_id": "G01", "category": "schedule"}],
        "matches": [] if parse_failed else [
            {"gen_risk_id": "R01", "gt_risk_id": "G01", "gen_category": "schedule",
             "gt_category": "schedule", "category_agree": True},
        ],
    }
    (dir_path / name).write_text(json.dumps(match_result), encoding="utf-8")


def _run_main(argv):
    with mock.patch.object(sys, "argv", ["metrics.py"] + argv):
        metrics.main()


class TestScoredDirArgument(unittest.TestCase):
    def test_reads_from_the_given_scored_dir_not_the_default(self):
        with tempfile.TemporaryDirectory() as td:
            scored_dir = Path(td) / "scored"
            scored_dir.mkdir()
            _write_match_file(scored_dir, "a.match.json")
            with mock.patch("sys.stdout") as mock_stdout:
                _run_main(["--scored-dir", str(scored_dir)])
            printed = "".join(c.args[0] for c in mock_stdout.write.call_args_list if c.args[0].strip())
        self.assertIn('"n_scored_runs_total": 1', printed)

    def test_missing_scored_dir_exits_one_with_a_message(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does_not_exist"
            with self.assertRaises(SystemExit) as cm:
                _run_main(["--scored-dir", str(missing)])
        self.assertEqual(cm.exception.code, 1)

    def test_empty_scored_dir_exits_one_same_as_missing(self):
        # compute_all() doesn't distinguish "directory exists but is empty"
        # from "directory doesn't exist" - both raise the same FileNotFoundError,
        # so both must be handled by the same except clause in main().
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "empty_scored"
            empty.mkdir()
            with self.assertRaises(SystemExit) as cm:
                _run_main(["--scored-dir", str(empty)])
        self.assertEqual(cm.exception.code, 1)


class TestOutArgument(unittest.TestCase):
    def test_out_omitted_writes_no_file_stdout_only(self):
        with tempfile.TemporaryDirectory() as td:
            scored_dir = Path(td) / "scored"
            scored_dir.mkdir()
            _write_match_file(scored_dir, "a.match.json")
            _run_main(["--scored-dir", str(scored_dir)])
            # No --out given: nothing should have been written anywhere else
            # in the temp dir besides the fixture file itself.
            written = sorted(p.name for p in Path(td).glob("*") if p.is_file())
        self.assertEqual(written, [])   # a.match.json is inside scored/, not td itself

    def test_out_given_writes_the_full_report_including_per_run(self):
        with tempfile.TemporaryDirectory() as td:
            scored_dir = Path(td) / "scored"
            scored_dir.mkdir()
            _write_match_file(scored_dir, "a.match.json")
            out_path = Path(td) / "metrics.json"
            _run_main(["--scored-dir", str(scored_dir), "--out", str(out_path)])
            self.assertTrue(out_path.exists())
            written = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertIn("per_run", written)
        self.assertEqual(len(written["per_run"]), 1)

    def test_stdout_summary_excludes_per_run_even_when_out_is_also_given(self):
        # main()'s own comment: "full per-run detail only goes to --out if
        # given, to keep stdout readable" - verify that split actually holds,
        # not just that both outputs individually look plausible.
        with tempfile.TemporaryDirectory() as td:
            scored_dir = Path(td) / "scored"
            scored_dir.mkdir()
            _write_match_file(scored_dir, "a.match.json")
            out_path = Path(td) / "metrics.json"
            with mock.patch("sys.stdout") as mock_stdout:
                _run_main(["--scored-dir", str(scored_dir), "--out", str(out_path)])
            printed = "".join(c.args[0] for c in mock_stdout.write.call_args_list if c.args[0].strip())
        self.assertNotIn('"per_run"', printed)
        self.assertIn('"n_scored_runs_total"', printed)

    def test_out_dir_is_created_if_it_does_not_exist_yet(self):
        with tempfile.TemporaryDirectory() as td:
            scored_dir = Path(td) / "scored"
            scored_dir.mkdir()
            _write_match_file(scored_dir, "a.match.json")
            out_path = Path(td) / "nested" / "not_yet_created" / "metrics.json"
            _run_main(["--scored-dir", str(scored_dir), "--out", str(out_path)])
            self.assertTrue(out_path.exists())


class TestMultipleFilesAndParseFailures(unittest.TestCase):
    def test_multiple_match_files_all_counted(self):
        with tempfile.TemporaryDirectory() as td:
            scored_dir = Path(td) / "scored"
            scored_dir.mkdir()
            _write_match_file(scored_dir, "a.match.json", project_id="P-A")
            _write_match_file(scored_dir, "b.match.json", project_id="P-B")
            _write_match_file(scored_dir, "c.match.json", project_id="P-C", parse_failed=True)
            out_path = Path(td) / "metrics.json"
            _run_main(["--scored-dir", str(scored_dir), "--out", str(out_path)])
            written = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(written["n_scored_runs_total"], 3)
        self.assertEqual(written["n_parse_failed_total"], 1)

    def test_non_match_json_files_in_the_directory_are_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            scored_dir = Path(td) / "scored"
            scored_dir.mkdir()
            _write_match_file(scored_dir, "a.match.json")
            (scored_dir / "readme.txt").write_text("not a match file", encoding="utf-8")
            (scored_dir / ".gitkeep").write_text("", encoding="utf-8")
            out_path = Path(td) / "metrics.json"
            _run_main(["--scored-dir", str(scored_dir), "--out", str(out_path)])
            written = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(written["n_scored_runs_total"], 1)


if __name__ == "__main__":
    unittest.main()
