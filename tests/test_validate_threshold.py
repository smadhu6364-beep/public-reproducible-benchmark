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
import re
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


class TestPairsFixtureGroundTruthIntegrity(unittest.TestCase):
    """Guards analysis/threshold_validation_pairs.json's own data integrity -
    this fixture drives the real MATCH_THRESHOLD value live in match.py, so a
    future edit quietly turning a "ground_truth"-labeled side into fabricated
    or paraphrased text (rather than real corpus language) would corrupt the
    justification behind that threshold.

    Corrected 2026-07-21: the fixture's own _meta.honest_scope originally
    claimed every ground_truth side was "VERBATIM" from the real registers.
    Checking all 24 programmatically found only 4 were exact full-field
    matches; most of the rest are excerpts truncated at a clause boundary
    (sometimes with the cut-point punctuation normalized to a period), and at
    least one has a short phrase excised from mid-sentence. None were
    fabricated. _meta and validate_threshold.py's docstring were corrected to
    say "real excerpt," not "verbatim." This test doesn't demand exact
    verbatim (that would be re-asserting the false claim) - it demands the
    weaker, still-meaningful property that actually matters: real text, not
    invented text. A description passes if it exactly matches, or if it
    shares a genuine verbatim run of >=40 characters with the real
    description (long enough that random/paraphrased text could not
    plausibly match by accident, per difflib's longest-matching-block).
    """

    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(vt.PAIRS_PATH.read_text(encoding="utf-8"))
        cls._gt_cache = {}

    def _load_gt(self, project_id):
        if project_id not in self._gt_cache:
            path = vt.REPO_ROOT / "data" / "ground_truth" / f"{project_id}.json"
            self._gt_cache[project_id] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        return self._gt_cache[project_id]

    def _register_project(self, register_field):
        m = re.match(r"(?:WB|UK):(P-[\w-]+)", register_field)
        return m.group(1) if m else None

    # XPROJ-NEG-02.b is a confirmed, pre-existing exception found 2026-07-21:
    # labeled "ground_truth R01" but actually reworded ("...implementation
    # momentum around the 2026 elections" vs. the real R01's "...implementation
    # momentum; further changes may follow the mid-2026 legislative/
    # parliamentary elections" - different words, not a truncation of the same
    # ones). Documented in the fixture's own _meta.honest_scope rather than
    # silently rewritten (that would be re-authoring research fixture data
    # already baked into the live MATCH_THRESHOLD justification). Allowlisted
    # here, once, with the reason on record, so the test stays a real guard
    # against a NEW instance of this without permanently failing on the one
    # already-known and disclosed case.
    KNOWN_REWORDED_NOT_EXCERPTED = {("XPROJ-NEG-02", "b")}

    def test_every_ground_truth_labeled_side_shares_a_real_verbatim_run(self):
        import difflib

        checked = 0
        failures = []
        for pair in self.fixture["pairs"]:
            default_pid = self._register_project(pair["register"])
            for side_key in ("a", "b"):
                side = pair[side_key]
                src = side.get("source", "")
                if "generated_style" in src or "ground_truth" not in src:
                    continue
                m = re.match(r"(P-[\w-]+)\s+ground_truth", src)
                pid = m.group(1) if m else default_pid
                rid_m = re.search(r"\b(R\d+)\b", src)
                self.assertIsNotNone(pid, f"{pair['pair_id']}.{side_key}: could not resolve project from {src!r}")
                self.assertIsNotNone(rid_m, f"{pair['pair_id']}.{side_key}: could not resolve risk_id from {src!r}")
                rid = rid_m.group(1)
                gt = self._load_gt(pid)
                self.assertIsNotNone(gt, f"{pair['pair_id']}.{side_key}: no ground-truth file for {pid}")
                risk = next((r for r in gt["risks"] if r["risk_id"] == rid), None)
                self.assertIsNotNone(risk, f"{pair['pair_id']}.{side_key}: {pid} has no risk {rid}")

                checked += 1
                if (pair["pair_id"], side_key) in self.KNOWN_REWORDED_NOT_EXCERPTED:
                    continue
                pd, gd = side["description"].strip(), risk["description"].strip()
                if pd == gd:
                    continue
                match = difflib.SequenceMatcher(None, pd, gd).find_longest_match(0, len(pd), 0, len(gd))
                if match.size < 40:
                    failures.append(f"{pair['pair_id']}.{side_key}: longest shared run only "
                                    f"{match.size} chars - looks fabricated/paraphrased, not excerpted")

        self.assertGreater(checked, 15, "sanity check: expected most of the 21 pairs to have >=1 ground_truth side")
        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
