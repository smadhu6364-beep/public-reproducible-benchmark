"""Unit tests for analysis/gen_synthetic_scored.py - previously zero coverage.

This script's own correctness matters even though its output is fake: it's
what Task C used to exercise the real match.py -> metrics.py -> figures chain
before any real experiment existed, and it's the thing standing between "the
pipeline works" and "the pipeline looks like it works because the fixture
happens to dodge every edge case." The self-consistency checks below (every
gen_risk_id/gt_risk_id referenced in `matches` must actually exist in
`gen_risks`/`gt_risks`) are exactly the kind of thing a hand-tuned fixture can
silently violate without anyone noticing, since match.py/metrics.py don't
necessarily crash on a dangling reference - they'd just produce quietly wrong
aggregate numbers.

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "analysis"
sys.path.insert(0, str(SRC))
import gen_synthetic_scored as gss  # noqa: E402


class TestBuildMatchRecordShape(unittest.TestCase):
    """The record shape must match what match.py.score_raw_output() actually
    produces, since metrics.py is exercised against this as a stand-in."""

    REQUIRED_KEYS = {"run_file", "project_id", "model", "prompt_strategy", "run_index",
                     "parse_failed", "embedding_model", "threshold", "matches",
                     "gen_risks", "gt_risks"}

    def test_ordinary_cell_has_every_required_key(self):
        rec = gss.build_match_record("P-SRB-CompetitivenessJobs", "claude", "structured", 1)
        self.assertEqual(set(rec), self.REQUIRED_KEYS)

    def test_parse_failed_cell_has_every_required_key(self):
        rec = gss.build_match_record("P-KHM-BasicEducationImprovement", "opensource", "zero_shot", 1)
        self.assertEqual(set(rec), self.REQUIRED_KEYS)
        self.assertTrue(rec["parse_failed"])
        self.assertEqual(rec["gen_risks"], [])
        self.assertEqual(rec["matches"], [])
        self.assertIsNone(rec["embedding_model"])


class TestBuildMatchRecordSelfConsistency(unittest.TestCase):
    """Every match must reference risk_ids that actually exist in gen_risks/
    gt_risks - a dangling reference here would silently corrupt whatever
    metrics.py/make_figures.py compute from it, without necessarily crashing."""

    def _all_cells(self):
        for project_id in gss.GT:
            for model in gss.MODELS:
                for prompt in gss.PROMPTS:
                    for run_index in (1, 2):
                        yield gss.build_match_record(project_id, model, prompt, run_index)

    def test_every_match_references_real_risk_ids(self):
        for rec in self._all_cells():
            gen_ids = {r["risk_id"] for r in rec["gen_risks"]}
            gt_ids = {r["risk_id"] for r in rec["gt_risks"]}
            for m in rec["matches"]:
                self.assertIn(m["gen_risk_id"], gen_ids,
                             f"{rec['run_file']}: match references unknown gen_risk_id {m['gen_risk_id']!r}")
                self.assertIn(m["gt_risk_id"], gt_ids,
                             f"{rec['run_file']}: match references unknown gt_risk_id {m['gt_risk_id']!r}")

    def test_matches_are_one_to_one(self):
        # A synthetic record claiming the same gen or gt risk matched twice
        # would misrepresent the greedy one-to-one invariant match.py itself
        # guarantees - the fixture must not accidentally violate it.
        for rec in self._all_cells():
            gen_ids_used = [m["gen_risk_id"] for m in rec["matches"]]
            gt_ids_used = [m["gt_risk_id"] for m in rec["matches"]]
            self.assertEqual(len(gen_ids_used), len(set(gen_ids_used)), f"{rec['run_file']}: gen risk matched twice")
            self.assertEqual(len(gt_ids_used), len(set(gt_ids_used)), f"{rec['run_file']}: gt risk matched twice")

    def test_category_agree_flag_matches_the_actual_categories(self):
        for rec in self._all_cells():
            for m in rec["matches"]:
                expected = m["gen_category"] == m["gt_category"]
                self.assertEqual(m["category_agree"], expected,
                                 f"{rec['run_file']}: category_agree flag inconsistent with gen/gt category")

    def test_no_generated_risk_has_category_other(self):
        # output_schema.json forbids "other" for generated risks - the
        # synthetic generator must respect the same constraint real model
        # output would be validated against.
        for rec in self._all_cells():
            for r in rec["gen_risks"]:
                self.assertNotEqual(r["category"], "other", f"{rec['run_file']}: generated risk has category=other")

    def test_gt_risks_are_always_the_real_fixture_for_that_project(self):
        for rec in self._all_cells():
            expected_ids = {r["risk_id"] for r in gss.GT[rec["project_id"]]}
            actual_ids = {r["risk_id"] for r in rec["gt_risks"]}
            self.assertEqual(actual_ids, expected_ids)


class TestSkillOrdering(unittest.TestCase):
    """Task C's design goal: RQ2 should be legible in the synthetic data -
    claude > gpt > opensource, structured > few_shot > zero_shot."""

    def _match_count(self, project_id, model, prompt):
        rec = gss.build_match_record(project_id, model, prompt, 1)
        return len(rec["matches"])

    def test_claude_matches_at_least_as_many_as_opensource(self):
        for prompt in gss.PROMPTS:
            claude_n = self._match_count("P-SRB-CompetitivenessJobs", "claude", prompt)
            opensource_n = self._match_count("P-SRB-CompetitivenessJobs", "opensource", prompt)
            self.assertGreaterEqual(claude_n, opensource_n,
                                    f"claude should match >= opensource under {prompt}")

    def test_structured_matches_at_least_as_many_as_zero_shot(self):
        for model in gss.MODELS:
            structured_n = self._match_count("P-SRB-CompetitivenessJobs", model, "structured")
            zero_shot_n = self._match_count("P-SRB-CompetitivenessJobs", model, "zero_shot")
            self.assertGreaterEqual(structured_n, zero_shot_n,
                                    f"structured should match >= zero_shot for {model}")


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_produce_identical_output(self):
        a = gss.build_match_record("P-SRB-CompetitivenessJobs", "gpt", "few_shot", 1)
        b = gss.build_match_record("P-SRB-CompetitivenessJobs", "gpt", "few_shot", 1)
        self.assertEqual(a, b)

    def test_run2_differs_from_run1(self):
        # The generator deliberately makes run2 hallucinate one extra, so
        # aggregation across runs isn't trivially identical.
        r1 = gss.build_match_record("P-SRB-CompetitivenessJobs", "gpt", "few_shot", 1)
        r2 = gss.build_match_record("P-SRB-CompetitivenessJobs", "gpt", "few_shot", 2)
        self.assertNotEqual(len(r1["gen_risks"]), len(r2["gen_risks"]))


class TestMainCLI(unittest.TestCase):
    def test_writes_expected_file_count_and_readme(self):
        # Assertions must stay INSIDE the TemporaryDirectory context - __exit__
        # deletes the temp tree, so checking .exists() afterward would always
        # read False regardless of what main() actually wrote.
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("sys.argv", ["gen_synthetic_scored.py", "--out-dir", td, "--runs", "2"]):
                gss.main()
            files = sorted(Path(td).glob("*.match.json"))
            readme = Path(td) / "_README_SYNTHETIC.txt"
            expected_n = len(gss.GT) * len(gss.MODELS) * len(gss.PROMPTS) * 2
            self.assertEqual(len(files), expected_n)
            self.assertTrue(readme.exists())
            self.assertIn("SYNTHETIC", readme.read_text(encoding="utf-8"))

    def test_stale_files_are_cleared_before_a_fresh_run(self):
        with tempfile.TemporaryDirectory() as td:
            stale = Path(td) / "leftover_project__x__y__run9.match.json"
            Path(td).mkdir(parents=True, exist_ok=True)
            stale.write_text("{}", encoding="utf-8")
            with mock.patch("sys.argv", ["gen_synthetic_scored.py", "--out-dir", td, "--runs", "1"]):
                gss.main()
            self.assertFalse(stale.exists())

    def test_every_written_file_is_valid_json_matching_the_filename(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("sys.argv", ["gen_synthetic_scored.py", "--out-dir", td, "--runs", "1"]):
                gss.main()
            for f in Path(td).glob("*.match.json"):
                rec = json.loads(f.read_text(encoding="utf-8"))
                self.assertEqual(f.name, f"{rec['project_id']}__{rec['model']}__{rec['prompt_strategy']}__run{rec['run_index']}.match.json")


if __name__ == "__main__":
    unittest.main()
