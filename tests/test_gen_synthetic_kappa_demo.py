"""Tests for analysis/gen_synthetic_kappa_demo.py - confirms the synthetic
fixture runs through the REAL compute_kappa.compute_report() and produces a
complete, clearly-labeled demo report, without asserting on the specific
fabricated numbers (those aren't the point - the shape and labeling are).

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = REPO_ROOT / "analysis"
sys.path.insert(0, str(ANALYSIS))
sys.path.insert(0, str(REPO_ROOT / "src"))
import gen_synthetic_kappa_demo as demo  # noqa: E402
import compute_kappa as ck  # noqa: E402


class TestSyntheticFixtureShape(unittest.TestCase):
    def test_blinding_map_covers_all_9_cells_twice_each(self):
        bm = demo.build_synthetic_blinding_map()
        self.assertEqual(len(bm), 18)
        cells = [(v["model"], v["prompt_strategy"]) for v in bm.values()]
        for model in ck.MODELS:
            for prompt in ck.PROMPTS:
                self.assertEqual(cells.count((model, prompt)), 2)

    def test_ratings_cover_every_code_for_every_rater(self):
        bm = demo.build_synthetic_blinding_map()
        ratings = demo.build_synthetic_ratings(bm)
        self.assertEqual(set(ratings.keys()), {"rater_a", "rater_b", "rater_c"})
        for rater_id, codes in ratings.items():
            self.assertEqual(set(codes.keys()), set(bm.keys()))
            for code, vals in codes.items():
                for dim in ck.DIMENSIONS:
                    self.assertIn(vals[dim], ck.CATEGORIES)

    def test_runs_through_the_real_compute_report_without_error(self):
        bm = demo.build_synthetic_blinding_map()
        ratings = demo.build_synthetic_ratings(bm)
        report = ck.compute_report(ratings, bm)  # must not raise
        self.assertEqual(report["n_registers_rated"], 18)
        self.assertEqual(report["n_raters"], 3)
        for label in ck.DIMENSIONS.values():
            self.assertIn(label, report["overall"])


class TestMainWritesLabeledOutput(unittest.TestCase):
    def test_out_file_has_synthetic_warning_and_full_report(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "demo.json"
            import unittest.mock as mock
            argv = ["gen_synthetic_kappa_demo.py", "--out", str(out_path)]
            with mock.patch.object(sys, "argv", argv):
                exit_code = demo.main()
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_path.exists())
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("_SYNTHETIC_WARNING", data)
            self.assertIn("FABRICATED", data["_SYNTHETIC_WARNING"].upper())
            self.assertIn("overall", data)
            self.assertEqual(data["n_registers_rated"], 18)

            readme = out_path.parent / "_README_SYNTHETIC.txt"
            self.assertTrue(readme.exists())
            self.assertIn("synthetic_kappa", readme.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
