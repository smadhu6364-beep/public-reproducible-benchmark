"""Unit tests for src/match.py's matching logic.

Uses a stubbed embedding model (pre-computed vectors) so the greedy,
highest-similarity-first, one-to-one matching and the threshold boundary are
tested deterministically without downloading sentence-transformers. This is the
code path match.py's own docstring says should be unit-testable "with
pre-computed embeddings". Run: python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import match  # noqa: E402


class _StubModel:
    """Returns a fixed vector per exact input text; raises on an unmapped text
    so a test can't silently pass on a typo."""

    def __init__(self, vec_map):
        self.vec_map = vec_map

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False):
        return np.array([self.vec_map[t] for t in texts], dtype=float)


def _risk(rid, desc, cat, mit=""):
    return {"risk_id": rid, "description": desc, "category": cat, "mitigation": mit}


class TestRiskText(unittest.TestCase):
    def test_concatenates_description_and_mitigation(self):
        self.assertEqual(match.risk_text({"description": "a", "mitigation": "b"}), "a b")

    def test_missing_mitigation(self):
        self.assertEqual(match.risk_text({"description": "a"}), "a")

    def test_none_mitigation(self):
        self.assertEqual(match.risk_text({"description": "a", "mitigation": None}), "a")


class TestCosineMatrix(unittest.TestCase):
    def test_identical_vectors_cosine_one(self):
        m = match._cosine_matrix([[1.0, 0.0]], [[2.0, 0.0]])  # same direction
        self.assertAlmostEqual(float(m[0, 0]), 1.0, places=5)

    def test_orthogonal_vectors_cosine_zero(self):
        m = match._cosine_matrix([[1.0, 0.0]], [[0.0, 1.0]])
        self.assertAlmostEqual(float(m[0, 0]), 0.0, places=5)


class TestMatchProject(unittest.TestCase):
    def _run(self, generated, ground_truth, vec_map, threshold):
        stub = _StubModel(vec_map)
        with mock.patch.object(match, "_get_model", return_value=stub):
            return match.match_project(generated, ground_truth, threshold=threshold)

    def test_one_to_one_greedy_and_category_agree(self):
        gen = {"risks": [_risk("R01", "delay", "schedule"), _risk("R02", "cost", "financial")]}
        gt = {"project_id": "P", "risks": [_risk("G01", "delay", "schedule"), _risk("G02", "cost", "organizational")]}
        vec_map = {
            "delay": [1.0, 0.0],   # gen R01 and gt G01 both "delay" -> cosine 1.0
            "cost": [0.0, 1.0],    # gen R02 and gt G02 both "cost" -> cosine 1.0
        }
        res = self._run(gen, gt, vec_map, threshold=0.45)
        pairs = {(m["gen_risk_id"], m["gt_risk_id"]): m for m in res["matches"]}
        self.assertEqual(set(pairs), {("R01", "G01"), ("R02", "G02")})
        self.assertTrue(pairs[("R01", "G01")]["category_agree"])       # schedule == schedule
        self.assertFalse(pairs[("R02", "G02")]["category_agree"])      # financial != organizational

    def test_threshold_excludes_below(self):
        gen = {"risks": [_risk("R01", "gx", "schedule")]}
        gt = {"project_id": "P", "risks": [_risk("G01", "gy", "schedule")]}
        # cosine ~0.4 (below 0.45): construct vectors with that angle
        vec_map = {"gx": [1.0, 0.0], "gy": [0.4, np.sqrt(1 - 0.4**2)]}
        res = self._run(gen, gt, vec_map, threshold=0.45)
        self.assertEqual(res["matches"], [])

    def test_threshold_includes_at_or_above(self):
        gen = {"risks": [_risk("R01", "gx", "schedule")]}
        gt = {"project_id": "P", "risks": [_risk("G01", "gy", "schedule")]}
        vec_map = {"gx": [1.0, 0.0], "gy": [1.0, 0.0]}  # cosine 1.0
        res = self._run(gen, gt, vec_map, threshold=0.45)
        self.assertEqual(len(res["matches"]), 1)

    def test_greedy_prefers_higher_similarity(self):
        # One gen risk close to G01 (0.9) and less to G02; must take the higher pair.
        gen = {"risks": [_risk("R01", "g", "schedule")]}
        gt = {"project_id": "P",
              "risks": [_risk("G01", "close", "schedule"), _risk("G02", "far", "schedule")]}
        vec_map = {"g": [1.0, 0.0], "close": [0.95, np.sqrt(1 - 0.95**2)], "far": [0.5, np.sqrt(1 - 0.5**2)]}
        res = self._run(gen, gt, vec_map, threshold=0.45)
        self.assertEqual(len(res["matches"]), 1)
        self.assertEqual(res["matches"][0]["gt_risk_id"], "G01")

    def test_empty_generated_returns_no_matches(self):
        gt = {"project_id": "P", "risks": [_risk("G01", "x", "schedule")]}
        res = match.match_project({"risks": []}, gt, threshold=0.45)
        self.assertEqual(res["matches"], [])
        self.assertEqual(res["gt_risks"], gt["risks"])


class TestParseRawOutputFilename(unittest.TestCase):
    def test_valid_name(self):
        d = match.parse_raw_output_filename(Path("P-SRB-X__claude__zero_shot__run2.json"))
        self.assertEqual(d, {"project_id": "P-SRB-X", "model": "claude", "prompt": "zero_shot", "run": 2})

    def test_invalid_name_returns_none(self):
        self.assertIsNone(match.parse_raw_output_filename(Path("not-a-valid-name.json")))


if __name__ == "__main__":
    unittest.main()
