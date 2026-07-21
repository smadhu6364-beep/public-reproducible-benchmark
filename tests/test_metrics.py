"""Unit tests for src/metrics.py's metric computation.

Covers the arithmetic (recall/precision/category-accuracy with the correct
division-by-zero guards), the parse_failed path, and the model/prompt/category
aggregations. Two behaviours flagged in results/metrics_review_findings.md
were pinned here as CHARACTERIZATION tests before a decision existed
(documenting current behaviour, not asserting it was the final choice) - both
are now DECIDED (2026-07-21, Madhu): report both ways for each. The original
characterization test stays (it documents the still-default/unfiltered
behavior, now confirmed intentional rather than incidental); the new
TestComputeAllScopeAndParseFailureVariants class below tests the added
"_corpus_wide_only" / "_excluding_parse_failures" variants at the compute_all()
level, where the actual filtering decision lives.
Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import metrics  # noqa: E402


def _match_result(project_id, model, prompt, run_index, gen, gt, matches, parse_failed=False):
    return {
        "project_id": project_id, "model": model, "prompt_strategy": prompt,
        "run_index": run_index, "parse_failed": parse_failed,
        "gen_risks": gen, "gt_risks": gt, "matches": matches,
    }


def _m(gen_id, gt_id, gen_cat, gt_cat):
    return {"gen_risk_id": gen_id, "gt_risk_id": gt_id,
            "gen_category": gen_cat, "gt_category": gt_cat,
            "category_agree": gen_cat == gt_cat}


class TestRunMetrics(unittest.TestCase):
    def test_recall_precision_category_accuracy(self):
        gen = [{"risk_id": "R01", "category": "schedule"},
               {"risk_id": "R02", "category": "financial"},
               {"risk_id": "R03", "category": "technical"}]   # R03 hallucinated
        gt = [{"risk_id": "G01", "category": "schedule"},
              {"risk_id": "G02", "category": "organizational"},   # G02 missed
              {"risk_id": "G03", "category": "financial"}]
        matches = [_m("R01", "G01", "schedule", "schedule"),
                   _m("R02", "G03", "financial", "financial")]
        r = metrics.run_metrics(_match_result("P", "claude", "zero_shot", 1, gen, gt, matches))
        self.assertEqual(r["n_matched"], 2)
        self.assertAlmostEqual(r["precision"], 2 / 3, places=3)   # 2 of 3 generated matched
        self.assertAlmostEqual(r["recall"], 2 / 3, places=3)      # 2 of 3 ground-truth matched
        self.assertEqual(r["category_accuracy_of_matches"], 1.0)  # both matches agree
        self.assertEqual(r["missed_ground_truth_categories"], ["organizational"])
        self.assertEqual(r["unsupported_generated_categories"], ["technical"])

    def test_parse_failed_run_precision_none_recall_zero(self):
        gt = [{"risk_id": "G01", "category": "schedule"}]
        r = metrics.run_metrics(_match_result("P", "gpt", "zero_shot", 1, [], gt, [], parse_failed=True))
        self.assertIsNone(r["precision"])   # no generated risks -> precision undefined
        self.assertEqual(r["recall"], 0.0)  # nothing matched of a non-empty ground truth

    def test_empty_ground_truth_recall_none(self):
        gen = [{"risk_id": "R01", "category": "schedule"}]
        r = metrics.run_metrics(_match_result("P", "gpt", "zero_shot", 1, gen, [], []))
        self.assertIsNone(r["recall"])


class TestSafeMean(unittest.TestCase):
    def test_drops_none(self):
        self.assertEqual(metrics._safe_mean([None, 1.0, 2.0]), 1.5)

    def test_all_none_returns_none(self):
        self.assertIsNone(metrics._safe_mean([None, None]))

    def test_empty_returns_none(self):
        self.assertIsNone(metrics._safe_mean([]))


class TestAggregations(unittest.TestCase):
    def _per_run(self):
        # Two runs of one ordinary project + one run of a subgroup project.
        return [
            metrics.run_metrics(_match_result(
                "P-SRB-CompetitivenessJobs", "claude", "zero_shot", 1,
                [{"risk_id": "R01", "category": "schedule"}],
                [{"risk_id": "G01", "category": "schedule"}],
                [_m("R01", "G01", "schedule", "schedule")])),
            metrics.run_metrics(_match_result(
                "P-KHM-BasicEducationImprovement", "claude", "zero_shot", 1,
                [{"risk_id": "R01", "category": "financial"}],   # hallucination
                [{"risk_id": "G01", "category": "environmental"}],  # missed
                [])),
        ]

    def test_by_model_prompt_groups(self):
        out = metrics.aggregate_by_model_prompt(self._per_run())
        self.assertIn("claude / zero_shot", out)
        self.assertEqual(out["claude / zero_shot"]["n_runs"], 2)

    def test_by_category_counts(self):
        out = metrics.aggregate_by_category(self._per_run())
        self.assertEqual(out["environmental"]["missed_count"], 1)     # KHM G01 missed
        self.assertEqual(out["financial"]["hallucinated_count"], 1)   # KHM R01 hallucinated

    def test_subgroup_reported_separately(self):
        report = metrics.short_register_subgroup_report(self._per_run())
        # Only the KHM run is in the subgroup.
        self.assertEqual(report["n_runs"], 1)
        self.assertIn("P-KHM-BasicEducationImprovement", report["by_project"])
        self.assertNotIn("P-SRB-CompetitivenessJobs", report["by_project"])

    def test_characterization_parse_failure_counts_as_category_miss(self):
        # DECIDED 2026-07-21 (Madhu, resolving Finding 2 in
        # results/metrics_review_findings.md): report both ways. This is no
        # longer just a characterization of incidental behavior - it's the
        # confirmed, intentional default of aggregate_by_category()/by_category
        # in compute_all(). The cleaner signal excluding parse failures is the
        # separate by_category_excluding_parse_failures key - see
        # TestComputeAllScopeAndParseFailureVariants below.
        per_run = [metrics.run_metrics(_match_result(
            "P-X", "gpt", "zero_shot", 1, [],
            [{"risk_id": "G01", "category": "political_regulatory"}], [], parse_failed=True))]
        out = metrics.aggregate_by_category(per_run)
        self.assertEqual(out["political_regulatory"]["missed_count"], 1)


class TestComputeAllScopeAndParseFailureVariants(unittest.TestCase):
    """compute_all() reads *.match.json from a directory, so these write small
    fixture files to a temp dir rather than testing in-memory - covers the
    2026-07-21 Madhu decisions on results/metrics_review_findings.md Findings
    1 and 2 at the level they actually apply (compute_all()'s call pattern,
    not the lower-level aggregate_* functions, which are intentionally
    unchanged and still tested directly above)."""

    def _write_match_file(self, tmp_path, name, project_id, model, prompt, gen, gt, matches, parse_failed=False):
        payload = _match_result(project_id, model, prompt, 1, gen, gt, matches, parse_failed=parse_failed)
        with open(tmp_path / name, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_corpus_wide_only_variants_exclude_subgroup(self):
        # NOTE: aggregate_by_category only lists a category if it has a
        # nonzero missed_count or hallucinated_count SOMEWHERE - a clean
        # match contributes to neither dict and never appears as a key. So
        # fixtures below deliberately include a genuine miss/hallucination in
        # each run, not just a clean match, or there would be nothing to
        # assert presence/absence of.
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            # Ordinary project: R01 matches G01 (schedule); R02 is an unmatched
            # hallucination (technical) - "technical" should survive subgroup exclusion.
            self._write_match_file(
                tmp_path, "a.match.json", "P-SRB-CompetitivenessJobs", "claude", "zero_shot",
                [{"risk_id": "R01", "category": "schedule"}, {"risk_id": "R02", "category": "technical"}],
                [{"risk_id": "G01", "category": "schedule"}],
                [_m("R01", "G01", "schedule", "schedule")],
            )
            # Subgroup (KHM) project: nothing matches - "environmental" (missed)
            # and "financial" (hallucinated) should both disappear when excluded.
            self._write_match_file(
                tmp_path, "b.match.json", "P-KHM-BasicEducationImprovement", "claude", "zero_shot",
                [{"risk_id": "R01", "category": "financial"}],
                [{"risk_id": "G01", "category": "environmental"}],
                [],
            )
            report = metrics.compute_all(scored_dir=tmp_path)

            # Default (full corpus) RQ2/RQ3 include both runs.
            self.assertEqual(report["by_model_and_prompt"]["claude / zero_shot"]["n_runs"], 2)
            self.assertIn("environmental", report["by_category"])
            self.assertIn("financial", report["by_category"])
            self.assertIn("technical", report["by_category"])

            # corpus_wide_only variants exclude the KHM subgroup run entirely.
            self.assertEqual(report["by_model_and_prompt_corpus_wide_only"]["claude / zero_shot"]["n_runs"], 1)
            self.assertNotIn("environmental", report["by_category_corpus_wide_only"])
            self.assertNotIn("financial", report["by_category_corpus_wide_only"])
            self.assertIn("technical", report["by_category_corpus_wide_only"])

    def test_excluding_parse_failures_variant_drops_parse_failed_runs(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            # "ok" run: R01 matches G01 (schedule); R02 is an unmatched
            # hallucination (technical) - this is the run that must survive.
            self._write_match_file(
                tmp_path, "ok.match.json", "P-SRB-CompetitivenessJobs", "claude", "zero_shot",
                [{"risk_id": "R01", "category": "schedule"}, {"risk_id": "R02", "category": "technical"}],
                [{"risk_id": "G01", "category": "schedule"}],
                [_m("R01", "G01", "schedule", "schedule")],
            )
            self._write_match_file(
                tmp_path, "failed.match.json", "P-SRB-CompetitivenessJobs", "gpt", "zero_shot",
                [], [{"risk_id": "G01", "category": "political_regulatory"}], [], parse_failed=True,
            )
            report = metrics.compute_all(scored_dir=tmp_path)

            # Default by_category counts the parse failure's category as missed.
            self.assertEqual(report["by_category"]["political_regulatory"]["missed_count"], 1)
            self.assertIn("technical", report["by_category"])
            # The excluding-parse-failures variant drops the parse failure's
            # category entirely, but keeps the parse-passing run's signal.
            self.assertNotIn("political_regulatory", report["by_category_excluding_parse_failures"])
            self.assertIn("technical", report["by_category_excluding_parse_failures"])


if __name__ == "__main__":
    unittest.main()
