"""Smoke test for analysis/gen_synthetic_cutoff_report.py (F5): confirms the
demo script actually runs end to end and produces a report exercising all
three of pretraining_cutoff_report()'s buckets (pre_cutoff/post_cutoff/
undated) against the real corpus_manifest.csv's real publication_date gap -
not just that it doesn't crash.

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ANALYSIS = Path(__file__).resolve().parent.parent / "analysis"
sys.path.insert(0, str(ANALYSIS))
import gen_synthetic_cutoff_report as gscr  # noqa: E402


class TestBuildSyntheticPerRun(unittest.TestCase):
    def test_produces_one_record_per_project_model_prompt_run(self):
        per_run = gscr.build_synthetic_per_run(runs_per_cell=2)
        # 2 projects x 3 models x 3 prompts x 2 runs
        self.assertEqual(len(per_run), 2 * 3 * 3 * 2)

    def test_every_record_has_the_fields_pretraining_cutoff_report_needs(self):
        per_run = gscr.build_synthetic_per_run(runs_per_cell=1)
        for r in per_run:
            self.assertIn("project_id", r)
            self.assertIn("model", r)
            self.assertIn("recall", r)
            self.assertIn("precision", r)


class TestMainProducesAllThreeBuckets(unittest.TestCase):
    """The whole point of reusing gen_synthetic_scored.py's 2 real project_ids
    is that the REAL corpus_manifest.csv has a publication_date for one
    (P-SRB-CompetitivenessJobs) and not the other (P-KHM-...) - this demo
    should exercise pre_cutoff, post_cutoff, AND undated without needing to
    fabricate manifest rows of its own."""

    def _run(self, tmp_out):
        with mock.patch.object(sys, "argv", ["gen_synthetic_cutoff_report.py", "--out", str(tmp_out)]):
            code = gscr.main()
        return code, json.loads(tmp_out.read_text(encoding="utf-8"))

    def test_all_three_buckets_populated(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "report.json"
            code, report = self._run(out_path)
        self.assertEqual(code, 0)
        self.assertGreater(report["pre_cutoff"]["n_runs"], 0)
        self.assertGreater(report["post_cutoff"]["n_runs"], 0)
        self.assertGreater(report["n_runs_undated"], 0)

    def test_undated_bucket_is_exactly_the_project_with_no_publication_date(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "report.json"
            _, report = self._run(out_path)
        self.assertEqual(report["undated_projects"], ["P-KHM-BasicEducationImprovement"])

    def test_output_carries_a_synthetic_warning_and_the_placeholder_cutoffs_used(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "report.json"
            _, report = self._run(out_path)
        self.assertIn("_SYNTHETIC_WARNING", report)
        self.assertIn("SYNTHETIC", report["_SYNTHETIC_WARNING"])
        self.assertEqual(report["model_cutoffs_used"], gscr.SYNTHETIC_PLACEHOLDER_MODEL_CUTOFFS)

    def test_readme_synthetic_written_alongside_the_report(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "report.json"
            self._run(out_path)
            readme = out_path.parent / "_README_SYNTHETIC.txt"
            self.assertTrue(readme.exists())
            self.assertIn("SYNTHETIC", readme.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
