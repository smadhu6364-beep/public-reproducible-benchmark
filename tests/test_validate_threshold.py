"""Unit tests for src/validate_threshold.py - previously zero automated
coverage despite being 350+ LOC of real statistics (sensitivity, specificity,
F1, Youden's J) that produced the evidence behind match.py's MATCH_THRESHOLD
change from 0.5 to 0.45. The embedding model is stubbed the same way
test_match.py stubs it, so these run with no network/download - EXCEPT
TestRunPilotEndToEnd's real-model test, see its own note.

Run: python -m unittest discover -s tests
Run including the slow real-model test: RUN_SLOW_TESTS=1 python -m unittest discover -s tests
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import validate_threshold as vt  # noqa: E402
import match  # noqa: E402


class _StubModel:
    def __init__(self, vec_map):
        self.vec_map = vec_map

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False):
        return np.array([self.vec_map[t] for t in texts], dtype=float)


class TestConcat(unittest.TestCase):
    def test_joins_description_and_mitigation(self):
        self.assertEqual(vt.concat({"description": "a", "mitigation": "b"}), "a b")

    def test_none_mitigation_omitted(self):
        self.assertEqual(vt.concat({"description": "a", "mitigation": None}), "a")

    def test_missing_mitigation_key(self):
        self.assertEqual(vt.concat({"description": "a"}), "a")


class TestSweep(unittest.TestCase):
    def _pairs(self):
        # 3 should-match pairs with sim 0.6/0.7/0.8, 3 should-not with 0.2/0.3/0.4
        return [
            {"expected_match": True, "sim": 0.6}, {"expected_match": True, "sim": 0.7},
            {"expected_match": True, "sim": 0.8},
            {"expected_match": False, "sim": 0.2}, {"expected_match": False, "sim": 0.3},
            {"expected_match": False, "sim": 0.4},
        ]

    def test_perfect_separation_at_a_threshold_in_the_gap(self):
        rows = vt.sweep(self._pairs(), [0.5], "sim")
        r = rows[0]
        self.assertEqual((r["tp"], r["fn"], r["fp"], r["tn"]), (3, 0, 0, 3))
        self.assertEqual(r["sensitivity"], 1.0)
        self.assertEqual(r["specificity"], 1.0)
        self.assertEqual(r["precision"], 1.0)
        self.assertEqual(r["f1"], 1.0)
        self.assertEqual(r["accuracy"], 1.0)
        self.assertEqual(r["youden_j"], 1.0)

    def test_threshold_at_the_extreme_high_end_misses_everything(self):
        rows = vt.sweep(self._pairs(), [0.95], "sim")
        r = rows[0]
        self.assertEqual((r["tp"], r["fn"], r["fp"], r["tn"]), (0, 3, 0, 3))
        self.assertEqual(r["sensitivity"], 0.0)
        self.assertIsNone(r["precision"])   # 0/0 -> None, not a crash or a fake 0
        self.assertEqual(r["f1"], 0.0)

    def test_threshold_at_the_extreme_low_end_accepts_everything(self):
        rows = vt.sweep(self._pairs(), [0.0], "sim")
        r = rows[0]
        self.assertEqual((r["tp"], r["fn"], r["fp"], r["tn"]), (3, 0, 3, 0))
        self.assertEqual(r["specificity"], 0.0)
        self.assertAlmostEqual(r["precision"], 0.5)

    def test_threshold_boundary_is_inclusive(self):
        # sim == threshold counts as a match ('>=' in the implementation).
        rows = vt.sweep(self._pairs(), [0.6], "sim")
        self.assertEqual(rows[0]["tp"], 3)   # the 0.6-similarity positive is still counted

    def test_sweeps_multiple_thresholds_in_order(self):
        rows = vt.sweep(self._pairs(), [0.1, 0.5, 0.9], "sim")
        self.assertEqual([r["threshold"] for r in rows], [0.1, 0.5, 0.9])


class TestDistribution(unittest.TestCase):
    def test_basic_stats(self):
        d = vt.distribution([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(d["n"], 4)
        self.assertEqual(d["min"], 1.0)
        self.assertEqual(d["max"], 4.0)
        self.assertEqual(d["mean"], 2.5)
        self.assertEqual(d["median"], 2.5)

    def test_empty_list_returns_empty_dict_not_a_crash(self):
        self.assertEqual(vt.distribution([]), {})


class TestRecommend(unittest.TestCase):
    def test_separable_reports_true_and_a_correct_gap_midpoint(self):
        pairs = [{"expected_match": True, "sim": 0.6}, {"expected_match": True, "sim": 0.8},
                 {"expected_match": False, "sim": 0.2}, {"expected_match": False, "sim": 0.4}]
        sweep_rows = vt.sweep(pairs, [0.3, 0.5, 0.7], "sim")
        rec = vt.recommend(pairs, "sim", sweep_rows)
        self.assertTrue(rec["separable"])
        self.assertEqual(rec["gap_low_max_negative"], 0.4)
        self.assertEqual(rec["gap_high_min_positive"], 0.6)
        self.assertAlmostEqual(rec["gap_midpoint"], 0.5)

    def test_overlapping_reports_false_and_no_midpoint(self):
        pairs = [{"expected_match": True, "sim": 0.3}, {"expected_match": True, "sim": 0.8},
                 {"expected_match": False, "sim": 0.2}, {"expected_match": False, "sim": 0.5}]
        sweep_rows = vt.sweep(pairs, [0.3, 0.5, 0.7], "sim")
        rec = vt.recommend(pairs, "sim", sweep_rows)
        self.assertFalse(rec["separable"])
        self.assertIsNone(rec["gap_midpoint"])

    def test_best_youden_and_best_f1_pick_the_actual_best_row(self):
        pairs = [{"expected_match": True, "sim": 0.6}, {"expected_match": True, "sim": 0.8},
                 {"expected_match": False, "sim": 0.2}, {"expected_match": False, "sim": 0.4}]
        sweep_rows = vt.sweep(pairs, [0.1, 0.5, 0.9], "sim")
        rec = vt.recommend(pairs, "sim", sweep_rows)
        # threshold 0.5 sits in the perfect-separation gap -> J=1.0, F1=1.0,
        # strictly better than 0.1 (accepts everything) or 0.9 (misses everything).
        self.assertEqual(rec["best_youden_threshold"], 0.5)
        self.assertEqual(rec["best_f1_threshold"], 0.5)


class TestEmbedPairs(unittest.TestCase):
    def test_computes_both_desc_plus_mit_and_desc_only_similarity(self):
        pairs = [{
            "pair_id": "p1", "tier": "clear_positive", "expected_match": True,
            "a": {"description": "delay", "mitigation": "stage work"},
            "b": {"description": "delay", "mitigation": "different mitigation text"},
        }]
        # desc+mit vectors differ (different mitigation) but desc-only vectors are identical.
        vec_map = {
            "delay stage work": [1.0, 0.0],
            "delay different mitigation text": [0.0, 1.0],
            "delay": [1.0, 1.0],
        }
        stub = _StubModel(vec_map)
        with mock.patch.object(match, "_get_model", return_value=stub):
            out = vt.embed_pairs(pairs, "fake-model")
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["sim_desc_plus_mit"], 0.0, places=4)   # orthogonal
        self.assertAlmostEqual(out[0]["sim_desc_only"], 1.0, places=4)      # identical text, same vector


class TestRunPilotEndToEnd(unittest.TestCase):
    def test_returns_none_if_pilot_file_missing(self):
        with mock.patch.object(vt, "PILOT_PATH", Path("does/not/exist.json")):
            self.assertIsNone(vt.run_pilot_endtoend([0.45]))

    @unittest.skipUnless(
        os.environ.get("RUN_SLOW_TESTS"),
        "real embedding model (~15s even warm, longer cold/first-download) - "
        "this suite is otherwise fully stubbed and fast by design (see README/"
        "run_playbook.md); opt in with RUN_SLOW_TESTS=1 to actually exercise it.",
    )
    def test_runs_against_the_real_committed_pilot_and_gt(self):
        # Uses the real, committed scratch/pilot_STP_zeroshot.json and the real
        # STP ground truth - exercises match.py's actual match_project() with
        # its real embedding model, so this test is slower and needs network
        # the first time (model download/cache), same tradeoff test_match.py
        # avoids by stubbing - deliberately NOT stubbed here since the whole
        # point of this function is an end-to-end check with the real model.
        if not vt.PILOT_PATH.exists() or not vt.STP_GT_PATH.exists():
            self.skipTest("pilot fixture or STP ground truth not present")
        result = vt.run_pilot_endtoend([0.45])
        self.assertIsNotNone(result)
        self.assertEqual(len(result["by_threshold"]), 1)
        self.assertIn("n_matched", result["by_threshold"][0])
        self.assertGreater(result["n_generated"], 0)
        self.assertGreater(result["n_ground_truth"], 0)


class TestBuildReportSmokeTest(unittest.TestCase):
    def test_report_contains_expected_sections_and_no_crash(self):
        pairs = [
            {"pair_id": "p1", "tier": "clear_positive", "expected_match": True,
             "sim_desc_plus_mit": 0.7, "sim_desc_only": 0.6},
            {"pair_id": "p2", "tier": "clear_negative", "expected_match": False,
             "sim_desc_plus_mit": 0.2, "sim_desc_only": 0.3},
            {"pair_id": "p3", "tier": "hard_case", "expected_match": True,
             "sim_desc_plus_mit": 0.5, "sim_desc_only": 0.4,
             "register": "P-STP", "human_label_confidence": "medium", "rationale": "borderline"},
        ]
        clear = [p for p in pairs if p["tier"] != "hard_case"]
        sweep_rows = vt.sweep(clear, [0.45], "sim_desc_plus_mit")
        rec = vt.recommend(clear, "sim_desc_plus_mit", sweep_rows)
        report = vt.build_report("fake-model", [0.45], pairs, sweep_rows, sweep_rows,
                                 rec, rec, pilot=None)
        self.assertIn("# Threshold & embedding-model validation report", report)
        self.assertIn("Hard / borderline cases", report)
        self.assertIn("p1", report)
        self.assertIn("p3", report)

    def test_report_includes_pilot_section_when_pilot_data_given(self):
        clear = [{"pair_id": "p1", "tier": "clear_positive", "expected_match": True,
                  "sim_desc_plus_mit": 0.7, "sim_desc_only": 0.6},
                 {"pair_id": "p2", "tier": "clear_negative", "expected_match": False,
                  "sim_desc_plus_mit": 0.2, "sim_desc_only": 0.3}]
        sweep_rows = vt.sweep(clear, [0.45], "sim_desc_plus_mit")
        rec = vt.recommend(clear, "sim_desc_plus_mit", sweep_rows)
        pilot = {"generated_file": "scratch/x.json", "n_generated": 2, "n_ground_truth": 3,
                 "by_threshold": [{"threshold": 0.45, "n_matched": 1, "n_generated": 2,
                                   "n_ground_truth": 3, "matches": [{"gen": "R01", "gt": "G01", "sim": 0.7}]}]}
        report = vt.build_report("fake-model", [0.45], clear, sweep_rows, sweep_rows, rec, rec, pilot)
        self.assertIn("End-to-end check", report)
        self.assertIn("R01->G01", report)


class TestShowHelper(unittest.TestCase):
    def test_outside_repo_path_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            shown = vt._show(Path(td) / "report.md")
        self.assertTrue(Path(shown).is_absolute())


if __name__ == "__main__":
    unittest.main()
