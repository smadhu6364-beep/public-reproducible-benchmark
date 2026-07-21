"""Unit tests for src/match.py's driver: score_raw_output() and the --all/--file
CLI in main(). test_match.py already covers the pure matching logic
(match_project, _cosine_matrix, risk_text); this file covers the layer that
reads a real raw_outputs/ file, finds its project's ground truth, and decides
what happens on a parse-failed generation or a missing project - the same
class of driver bug this session already found in run_experiments.py's
run_one/_finalize_run and judge.py's judge_one.

The embedding model is stubbed throughout (mock.patch.object(match,
"_get_model", ...)) so nothing here needs network or a real download.

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import match  # noqa: E402

REAL_PROJECT = "P-SRB-CompetitivenessJobs"


class _StubModel:
    """Maps known texts to vectors, defaults unmapped text to a fixed vector -
    the real ground truth for REAL_PROJECT has several risks with varied
    text, so tests only care about pinning one or two, not all of them."""

    def __init__(self, vec_map, default=(0.0, 1.0)):
        self.vec_map = vec_map
        self.default = default

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False):
        return np.array([self.vec_map.get(t, self.default) for t in texts], dtype=float)


_UNSET = object()   # distinguishes "no override given" from an explicit parsed_risks=None
                    # (a real parse-failure record) - conflating the two would make every
                    # "simulate a parse failure" call above silently test the happy path instead.


def _write_raw_output(path: Path, *, project_id=REAL_PROJECT, parsed_risks=_UNSET,
                      model="claude", prompt_strategy="zero_shot", run_index=1):
    if parsed_risks is _UNSET:
        parsed_risks = {"project_id": project_id, "risks": [
            {"risk_id": "R01", "description": "delay", "category": "schedule",
             "likelihood": 3, "impact": 4, "mitigation": "m"},
        ]}
    path.write_text(json.dumps({
        "project_id": project_id, "model": model, "prompt_strategy": prompt_strategy,
        "run_index": run_index, "parsed_risks": parsed_risks,
    }), encoding="utf-8")


class TestScoreRawOutputHappyPath(unittest.TestCase):
    def test_scores_against_the_real_project_ground_truth(self):
        stub = _StubModel({"delay m": (1.0, 0.0)})
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "a.json"
            _write_raw_output(raw_path)
            with mock.patch.object(match, "_get_model", return_value=stub):
                result = match.score_raw_output(raw_path)
        self.assertEqual(result["project_id"], REAL_PROJECT)
        self.assertFalse(result["parse_failed"])
        self.assertIn("gt_risks", result)
        self.assertGreater(len(result["gt_risks"]), 0)   # real ground truth was loaded

    def test_result_carries_run_metadata_from_the_record(self):
        stub = _StubModel({})
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "a.json"
            _write_raw_output(raw_path, model="gpt", prompt_strategy="structured", run_index=2)
            with mock.patch.object(match, "_get_model", return_value=stub):
                result = match.score_raw_output(raw_path)
        self.assertEqual(result["model"], "gpt")
        self.assertEqual(result["prompt_strategy"], "structured")
        self.assertEqual(result["run_index"], 2)
        self.assertEqual(result["run_file"], "a.json")


class TestScoreRawOutputParseFailed(unittest.TestCase):
    def test_parse_failed_generation_scores_as_zero_matches_not_a_crash(self):
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "a.json"
            _write_raw_output(raw_path, parsed_risks=None)
            # No embedding model should even be needed for a parse-failed run.
            with mock.patch.object(match, "_get_model", side_effect=AssertionError("must not be called")):
                result = match.score_raw_output(raw_path)
        self.assertTrue(result["parse_failed"])
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["gen_risks"], [])
        self.assertGreater(len(result["gt_risks"]), 0)   # ground truth is still loaded and reported
        self.assertIsNone(result["embedding_model"])


class TestScoreRawOutputMissingGroundTruth(unittest.TestCase):
    def test_missing_ground_truth_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "a.json"
            _write_raw_output(raw_path, project_id="P-DOES-NOT-EXIST")
            with self.assertRaises(FileNotFoundError):
                match.score_raw_output(raw_path)


class TestParseRawOutputFilenameIntegration(unittest.TestCase):
    def test_score_raw_output_does_not_depend_on_filename_matching_convention(self):
        # score_raw_output reads project_id from the FILE CONTENT, not the
        # filename - a file with an unconventional name must still score
        # correctly (parse_raw_output_filename is a separate sanity check,
        # used elsewhere, not a hard requirement here).
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "not-the-usual-naming-convention.json"
            _write_raw_output(raw_path, parsed_risks=None)
            result = match.score_raw_output(raw_path)
        self.assertEqual(result["project_id"], REAL_PROJECT)


class TestMainCLI(unittest.TestCase):
    def _run_main(self, argv):
        with mock.patch.object(sys, "argv", ["match.py"] + argv):
            match.main()

    def test_all_flag_scores_every_raw_output(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            out_dir = Path(td) / "scored"
            raw_dir.mkdir()
            _write_raw_output(raw_dir / "a.json", parsed_risks=None)
            _write_raw_output(raw_dir / "b.json", parsed_risks=None)
            with mock.patch.object(match, "RAW_OUTPUTS_DIR", raw_dir):
                self._run_main(["--all", "--out-dir", str(out_dir)])
            written = sorted(p.name for p in out_dir.glob("*.match.json"))
        self.assertEqual(written, ["a.match.json", "b.match.json"])

    def test_gitkeep_excluded_from_all(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            out_dir = Path(td) / "scored"
            raw_dir.mkdir()
            (raw_dir / ".gitkeep").write_text("", encoding="utf-8")
            _write_raw_output(raw_dir / "a.json", parsed_risks=None)
            with mock.patch.object(match, "RAW_OUTPUTS_DIR", raw_dir):
                self._run_main(["--all", "--out-dir", str(out_dir)])
            written = list(out_dir.glob("*.match.json"))
        self.assertEqual(len(written), 1)

    def test_file_flag_scores_a_single_file(self):
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "single.json"
            out_dir = Path(td) / "scored"
            _write_raw_output(raw_path, parsed_risks=None)
            self._run_main(["--file", str(raw_path), "--out-dir", str(out_dir)])
            written = list(out_dir.glob("*.match.json"))
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0].name, "single.match.json")

    def test_threshold_flag_is_honored(self):
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "single.json"
            out_dir = Path(td) / "scored"
            _write_raw_output(raw_path, parsed_risks=None)   # threshold irrelevant on parse_failed, but flag must parse
            self._run_main(["--file", str(raw_path), "--out-dir", str(out_dir), "--threshold", "0.6"])
            result = json.loads((out_dir / "single.match.json").read_text(encoding="utf-8"))
        self.assertEqual(result["threshold"], 0.6)

    def test_neither_all_nor_file_is_a_usage_error(self):
        with self.assertRaises(SystemExit):
            self._run_main([])

    def test_no_targets_found_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            raw_dir.mkdir()
            with mock.patch.object(match, "RAW_OUTPUTS_DIR", raw_dir):
                with self.assertRaises(SystemExit) as cm:
                    self._run_main(["--all", "--out-dir", str(Path(td) / "scored")])
        self.assertNotEqual(cm.exception.code, 0)

    def test_out_dir_outside_the_repo_does_not_crash(self):
        # Regression coverage for this file's own _show() fix.
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "single.json"
            out_dir = Path(td) / "outside" / "scored"
            _write_raw_output(raw_path, parsed_risks=None)
            self._run_main(["--file", str(raw_path), "--out-dir", str(out_dir)])
            self.assertTrue((out_dir / "single.match.json").exists())


if __name__ == "__main__":
    unittest.main()
