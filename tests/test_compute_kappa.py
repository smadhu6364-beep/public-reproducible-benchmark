"""Task G1 - tests for src/compute_kappa.py (Method B: Fleiss' kappa + mean
Likert scores from completed rater assignment sheets).

The formula itself is verified against an INDEPENDENTLY computed worked
example (hand-derived in this file's comments, re-derived via a completely
separate code path here, not copied from an external citation this session
cannot fully verify from memory - CLAUDE.md's "never fabricate data or
citations" rule applies to test fixtures too, not just paper content).

Run: python -m unittest discover -s tests
"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import compute_kappa as ck  # noqa: E402


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


ASSIGNMENT_FIELDS = ["packet_code", "completeness_1to5", "accuracy_1to5", "actionability_1to5", "notable_issues"]
BLINDING_FIELDS = ["code", "project_id", "model", "prompt_strategy", "run_index", "cell"]


class TestFleissKappaFormula(unittest.TestCase):
    def test_matches_independently_derived_worked_example(self):
        # 4 subjects, 3 raters, categories {1,2,3} (padded to the 5-category
        # matrix compute_kappa.py always uses). By hand:
        #   subject1=[1,1,1] subject2=[1,1,2] subject3=[2,2,3] subject4=[3,3,3]
        #   P_i = [1, 1/3, 1/3, 1]  ->  P_bar = 2.6667/4 = 0.666667
        #   p_1=5/12=0.416667, p_2=3/12=0.25, p_3=4/12=0.333333
        #   P_e_bar = 0.416667^2 + 0.25^2 + 0.333333^2 = 0.347222
        #   kappa = (0.666667 - 0.347222) / (1 - 0.347222) = 0.489362
        subjects = [[1, 1, 1], [1, 1, 2], [2, 2, 3], [3, 3, 3]]
        import numpy as np
        counts = np.array([[row.count(c) for c in ck.CATEGORIES] for row in subjects])
        kappa = ck.fleiss_kappa(counts)
        self.assertAlmostEqual(kappa, 0.4893617021276595, places=9)

    def test_perfect_agreement_is_exactly_1(self):
        import numpy as np
        # 3 subjects, 3 raters each, unanimous but varied across subjects
        # (so p_j isn't degenerate to one category).
        counts = np.array([[3, 0, 0, 0, 0], [0, 3, 0, 0, 0], [0, 0, 0, 3, 0]])
        self.assertEqual(ck.fleiss_kappa(counts), 1.0)

    def test_zero_variance_across_all_subjects_is_nan_not_a_crash(self):
        import numpy as np
        counts = np.array([[3, 0, 0, 0, 0], [3, 0, 0, 0, 0]])
        self.assertTrue(np.isnan(ck.fleiss_kappa(counts)))

    def test_raises_if_raters_per_subject_is_not_uniform(self):
        import numpy as np
        # subject 1 has 3 raters, subject 2 has only 2 - not a valid
        # fully-crossed design.
        counts = np.array([[3, 0, 0, 0, 0], [2, 0, 0, 0, 0]])
        with self.assertRaises(ValueError):
            ck.fleiss_kappa(counts)


class TestInterpretationBands(unittest.TestCase):
    def test_landis_koch_boundaries(self):
        self.assertEqual(ck.interpretation_band(-0.1), "poor")
        self.assertEqual(ck.interpretation_band(0.0), "slight")
        self.assertEqual(ck.interpretation_band(0.20), "slight")
        self.assertEqual(ck.interpretation_band(0.21), "fair")
        self.assertEqual(ck.interpretation_band(0.40), "fair")
        self.assertEqual(ck.interpretation_band(0.41), "moderate")
        self.assertEqual(ck.interpretation_band(0.60), "moderate")
        self.assertEqual(ck.interpretation_band(0.61), "substantial")
        self.assertEqual(ck.interpretation_band(0.80), "substantial")
        self.assertEqual(ck.interpretation_band(0.81), "almost perfect")
        self.assertEqual(ck.interpretation_band(1.0), "almost perfect")

    def test_nan_is_undefined_not_a_crash(self):
        import numpy as np
        self.assertEqual(ck.interpretation_band(float("nan")), "undefined (no rating variance)")


class TestLoadRaterAssignments(unittest.TestCase):
    def test_happy_path_parses_three_dimensions_and_notes(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_csv(d / "alice.csv", [
                {"packet_code": "REG-001", "completeness_1to5": "4", "accuracy_1to5": "3",
                 "actionability_1to5": "5", "notable_issues": "looks fabricated"},
            ], ASSIGNMENT_FIELDS)
            result = ck.load_rater_assignments(d)
            self.assertEqual(result["alice"]["REG-001"]["completeness_1to5"], 4)
            self.assertEqual(result["alice"]["REG-001"]["accuracy_1to5"], 3)
            self.assertEqual(result["alice"]["REG-001"]["actionability_1to5"], 5)
            self.assertEqual(result["alice"]["REG-001"]["notable_issues"], "looks fabricated")

    def test_blank_score_raises_with_rater_and_code_named(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_csv(d / "bob.csv", [
                {"packet_code": "REG-002", "completeness_1to5": "", "accuracy_1to5": "3",
                 "actionability_1to5": "5", "notable_issues": ""},
            ], ASSIGNMENT_FIELDS)
            with self.assertRaises(ValueError) as ctx:
                ck.load_rater_assignments(d)
            self.assertIn("bob.csv", str(ctx.exception))
            self.assertIn("REG-002", str(ctx.exception))

    def test_non_integer_score_raises(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_csv(d / "carol.csv", [
                {"packet_code": "REG-003", "completeness_1to5": "four", "accuracy_1to5": "3",
                 "actionability_1to5": "5", "notable_issues": ""},
            ], ASSIGNMENT_FIELDS)
            with self.assertRaises(ValueError):
                ck.load_rater_assignments(d)

    def test_out_of_range_score_raises(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_csv(d / "dave.csv", [
                {"packet_code": "REG-004", "completeness_1to5": "7", "accuracy_1to5": "3",
                 "actionability_1to5": "5", "notable_issues": ""},
            ], ASSIGNMENT_FIELDS)
            with self.assertRaises(ValueError):
                ck.load_rater_assignments(d)

    def test_missing_column_raises(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_csv(d / "erin.csv", [
                {"packet_code": "REG-005", "completeness_1to5": "3"},
            ], ["packet_code", "completeness_1to5"])
            with self.assertRaises(ValueError):
                ck.load_rater_assignments(d)

    def test_missing_directory_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            ck.load_rater_assignments(Path("/definitely/not/a/real/path/xyz"))

    def test_empty_directory_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                ck.load_rater_assignments(Path(td))


class TestValidateFullOverlap(unittest.TestCase):
    def test_matching_code_sets_returns_sorted_codes(self):
        ratings = {
            "alice": {"REG-002": {}, "REG-001": {}},
            "bob": {"REG-001": {}, "REG-002": {}},
        }
        self.assertEqual(ck.validate_full_overlap(ratings), ["REG-001", "REG-002"])

    def test_missing_code_for_one_rater_raises_and_names_it(self):
        ratings = {
            "alice": {"REG-001": {}, "REG-002": {}},
            "bob": {"REG-001": {}},  # missing REG-002
        }
        with self.assertRaises(ValueError) as ctx:
            ck.validate_full_overlap(ratings)
        self.assertIn("bob", str(ctx.exception))
        self.assertIn("REG-002", str(ctx.exception))

    def test_fewer_than_2_raters_raises(self):
        with self.assertRaises(ValueError):
            ck.validate_full_overlap({"alice": {"REG-001": {}}})


class TestComputeReport(unittest.TestCase):
    def _blinding_map(self):
        # 6 registers: 2 per model (claude/gpt/opensource), split zero_shot/few_shot.
        rows = [
            {"code": "REG-001", "project_id": "P-A", "model": "claude", "prompt_strategy": "zero_shot", "run_index": "1", "cell": "claude_zero_shot"},
            {"code": "REG-002", "project_id": "P-B", "model": "claude", "prompt_strategy": "few_shot", "run_index": "1", "cell": "claude_few_shot"},
            {"code": "REG-003", "project_id": "P-C", "model": "gpt", "prompt_strategy": "zero_shot", "run_index": "1", "cell": "gpt_zero_shot"},
            {"code": "REG-004", "project_id": "P-D", "model": "gpt", "prompt_strategy": "few_shot", "run_index": "1", "cell": "gpt_few_shot"},
            {"code": "REG-005", "project_id": "P-E", "model": "opensource", "prompt_strategy": "zero_shot", "run_index": "1", "cell": "opensource_zero_shot"},
            {"code": "REG-006", "project_id": "P-F", "model": "opensource", "prompt_strategy": "few_shot", "run_index": "1", "cell": "opensource_few_shot"},
        ]
        return {r["code"]: r for r in rows}

    def _ratings(self, notable_on_reg1=""):
        codes = ["REG-001", "REG-002", "REG-003", "REG-004", "REG-005", "REG-006"]
        # 3 raters, mostly-agreeing scores so kappa is well-defined and not degenerate.
        scores = {
            "REG-001": (4, 4, 3), "REG-002": (3, 3, 2), "REG-003": (5, 4, 5),
            "REG-004": (2, 2, 1), "REG-005": (4, 3, 4), "REG-006": (1, 1, 2),
        }
        raters = {"r1": {}, "r2": {}, "r3": {}}
        for code in codes:
            for i, rater_id in enumerate(["r1", "r2", "r3"]):
                raters[rater_id][code] = {
                    "completeness_1to5": scores[code][i],
                    "accuracy_1to5": scores[code][i],
                    "actionability_1to5": scores[code][i],
                    "notable_issues": notable_on_reg1 if (code == "REG-001" and rater_id == "r1") else "",
                }
        return raters

    def test_report_has_overall_by_model_by_prompt(self):
        report = ck.compute_report(self._ratings(), self._blinding_map())
        self.assertEqual(report["n_registers_rated"], 6)
        self.assertEqual(report["n_raters"], 3)
        for label in ck.DIMENSIONS.values():
            self.assertIn(label, report["overall"])
            self.assertIn("kappa", report["overall"][label])
            self.assertIn("mean_score", report["overall"][label])
        for model in ck.MODELS:
            self.assertIn(model, report["by_model"])
        for prompt in ck.PROMPTS:
            self.assertIn(prompt, report["by_prompt_strategy"])
        # 2 registers per model / per prompt in this fixture.
        self.assertEqual(report["by_model"]["claude"]["Completeness"]["n_registers"], 2)
        self.assertEqual(report["by_prompt_strategy"]["zero_shot"]["Completeness"]["n_registers"], 3)

    def test_notable_issues_collected_with_metadata(self):
        report = ck.compute_report(self._ratings(notable_on_reg1="looks fabricated"), self._blinding_map())
        self.assertEqual(len(report["notable_issues"]), 1)
        note = report["notable_issues"][0]
        self.assertEqual(note["rater_id"], "r1")
        self.assertEqual(note["code"], "REG-001")
        self.assertEqual(note["model"], "claude")
        self.assertEqual(note["note"], "looks fabricated")

    def test_unmapped_code_raises(self):
        blinding_map = self._blinding_map()
        del blinding_map["REG-001"]
        with self.assertRaises(ValueError):
            ck.compute_report(self._ratings(), blinding_map)


class TestMainCli(unittest.TestCase):
    def _write_fixture(self, root: Path):
        blinding_rows = [
            {"code": "REG-001", "project_id": "P-A", "model": "claude", "prompt_strategy": "zero_shot", "run_index": "1", "cell": "c"},
            {"code": "REG-002", "project_id": "P-B", "model": "gpt", "prompt_strategy": "few_shot", "run_index": "1", "cell": "c"},
        ]
        _write_csv(root / "blinding_map.csv", blinding_rows, BLINDING_FIELDS)
        assignments = root / "rater_assignments"
        for rater_id, vals in [("r1", (4, 3)), ("r2", (4, 2))]:
            rows = [
                {"packet_code": "REG-001", "completeness_1to5": str(vals[0]), "accuracy_1to5": str(vals[0]),
                 "actionability_1to5": str(vals[0]), "notable_issues": ""},
                {"packet_code": "REG-002", "completeness_1to5": str(vals[1]), "accuracy_1to5": str(vals[1]),
                 "actionability_1to5": str(vals[1]), "notable_issues": ""},
            ]
            _write_csv(assignments / f"{rater_id}.csv", rows, ASSIGNMENT_FIELDS)
        return assignments, root / "blinding_map.csv"

    def test_cli_writes_out_file_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            assignments, blinding = self._write_fixture(root)
            out_path = root / "kappa_report.json"
            argv = ["compute_kappa.py", "--assignments-dir", str(assignments),
                    "--blinding-map", str(blinding), "--out", str(out_path)]
            import unittest.mock as mock
            with mock.patch.object(sys, "argv", argv):
                exit_code = ck.main()
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_path.exists())
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(report["n_registers_rated"], 2)
            self.assertIn("notable_issues", report)  # only in the --out file, not stdout summary

    def test_cli_missing_assignments_dir_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            argv = ["compute_kappa.py", "--assignments-dir", str(Path(td) / "nope"),
                    "--blinding-map", str(Path(td) / "blinding_map.csv")]
            import unittest.mock as mock
            with mock.patch.object(sys, "argv", argv):
                exit_code = ck.main()
            self.assertEqual(exit_code, 1)

    def test_cli_incomplete_sheet_exits_1_with_clear_message(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            assignments, blinding = self._write_fixture(root)
            # Corrupt r2's sheet: blank out a score.
            rows = [
                {"packet_code": "REG-001", "completeness_1to5": "", "accuracy_1to5": "3",
                 "actionability_1to5": "3", "notable_issues": ""},
                {"packet_code": "REG-002", "completeness_1to5": "2", "accuracy_1to5": "2",
                 "actionability_1to5": "2", "notable_issues": ""},
            ]
            _write_csv(assignments / "r2.csv", rows, ASSIGNMENT_FIELDS)
            argv = ["compute_kappa.py", "--assignments-dir", str(assignments), "--blinding-map", str(blinding)]
            import unittest.mock as mock
            with mock.patch.object(sys, "argv", argv):
                exit_code = ck.main()
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
