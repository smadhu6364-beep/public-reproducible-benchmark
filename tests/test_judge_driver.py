"""Unit tests for judge.py's driver (judge_one, _default_judge_caller, main) -
the Method C code paths that only parse_judge_response/render_judge_prompt had
coverage for until now (see test_parsing.py).

Two things earned this file specifically:

1. `_default_judge_caller`'s call_fn wrapper had a REAL regression, already
   found and fixed 2026-07-21 (see judge.py's inline comment): it used to
   `return call_fn(...)` directly, handing judge_one a raw (text,
   temperature_applied) 2-tuple instead of the text - an AttributeError the
   first time anyone ran `judge.py --all` for real, since `.strip()` on a
   tuple fails immediately. That fix has never had a test pinning it, and the
   comment says outright this was "never exercised against a real API call" -
   exactly the kind of fix that's easy to silently re-break. Regression test
   below.

2. `judge_one` is judge.py's `_finalize_run` equivalent - the one place that
   decides what gets written and whether the (real, billed once keys exist)
   judge model gets called at all. It deserves the same scrutiny run_one's
   driver got in test_run_pipeline.py, particularly: does it correctly skip
   calling the judge model on an already-parse_failed generation (wasteful and
   meaningless otherwise), and does the rendered prompt avoid ground-truth
   leakage the same way run_experiments.py's does.

Everything here is stubbed - no network, no keys, no spend.

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
import judge  # noqa: E402

REAL_PROJECT = "P-SRB-CompetitivenessJobs"

VALID_REGISTER = {
    "project_id": REAL_PROJECT,
    "risks": [{
        "risk_id": "R01", "description": "A concrete risk.", "category": "schedule",
        "likelihood": 3, "impact": 4, "mitigation": "A concrete mitigation.",
        "evidence": "Sec III.",
    }],
}

VALID_JUDGE_JSON = json.dumps({"completeness": 4, "accuracy": 3, "actionability": 5,
                               "overall": 4, "rationale": "Solid coverage."})


def _write_raw_output(tmp: Path, name: str, *, project_id=REAL_PROJECT,
                      parsed_risks=VALID_REGISTER, model="claude", prompt_strategy="zero_shot", run_index=1):
    p = tmp / name
    p.write_text(json.dumps({
        "project_id": project_id, "model": model, "prompt_strategy": prompt_strategy,
        "run_index": run_index, "parsed_risks": parsed_risks,
    }), encoding="utf-8")
    return p


class TestJudgeOneHappyPath(unittest.TestCase):
    def test_calls_judge_model_and_records_scores(self):
        calls = []

        def fake_caller(prompt):
            calls.append(prompt)
            return VALID_JUDGE_JSON

        with tempfile.TemporaryDirectory() as td:
            raw_path = _write_raw_output(Path(td), "a.json")
            result = judge.judge_one(raw_path, fake_caller)

        self.assertTrue(result["judged"])
        self.assertIsNone(result["parse_error"])
        self.assertEqual(result["scores"]["accuracy"], 3)
        self.assertEqual(result["project_id"], REAL_PROJECT)
        self.assertEqual(result["generation_model"], "claude")
        self.assertEqual(result["generation_prompt_strategy"], "zero_shot")
        self.assertEqual(result["generation_run_index"], 1)
        self.assertEqual(result["run_file"], "a.json")
        self.assertEqual(len(calls), 1)

    def test_prompt_sent_to_judge_contains_planning_text_and_the_register(self):
        captured = {}

        def fake_caller(prompt):
            captured["prompt"] = prompt
            return VALID_JUDGE_JSON

        with tempfile.TemporaryDirectory() as td:
            raw_path = _write_raw_output(Path(td), "a.json")
            judge.judge_one(raw_path, fake_caller)

        # Real planning text for this project must actually be in the prompt.
        planning = (judge.PROCESSED_DIR / f"{REAL_PROJECT}.txt").read_text(encoding="utf-8")
        self.assertIn(planning.strip()[:200], captured["prompt"])
        self.assertIn("R01", captured["prompt"])  # the generated register


class TestJudgeOneSkipsParseFailedGenerations(unittest.TestCase):
    def test_parse_failed_generation_is_not_sent_to_the_judge_model_at_all(self):
        # generated risks are None -> nothing meaningful to judge. Must not
        # waste a (real, billed) judge call on it.
        calls = []
        fake_caller = lambda prompt: calls.append(prompt) or VALID_JUDGE_JSON

        with tempfile.TemporaryDirectory() as td:
            raw_path = _write_raw_output(Path(td), "a.json", parsed_risks=None)
            result = judge.judge_one(raw_path, fake_caller)

        self.assertFalse(result["judged"])
        self.assertIn("parse_failed", result["reason"])
        self.assertEqual(calls, [], "judge model must not be called for a parse_failed generation")
        self.assertNotIn("scores", result)


class TestJudgeOneHandlesAMalformedJudgeResponse(unittest.TestCase):
    def test_unparseable_judge_response_is_recorded_not_raised(self):
        fake_caller = lambda prompt: "I refuse to output JSON today."

        with tempfile.TemporaryDirectory() as td:
            raw_path = _write_raw_output(Path(td), "a.json")
            result = judge.judge_one(raw_path, fake_caller)

        self.assertFalse(result["judged"])
        self.assertIsNone(result["scores"])
        self.assertIsNotNone(result["parse_error"])
        self.assertIn("refuse", result["raw_judge_response"])  # raw text always preserved

    def test_bool_as_int_from_judge_model_is_rejected(self):
        # The bool-as-int gotcha end to end through judge_one, not just
        # parse_judge_response in isolation.
        bad = json.dumps({"completeness": True, "accuracy": 3, "actionability": 5, "overall": 4})
        with tempfile.TemporaryDirectory() as td:
            raw_path = _write_raw_output(Path(td), "a.json")
            result = judge.judge_one(raw_path, lambda p: bad)
        self.assertFalse(result["judged"])
        self.assertIn("completeness", result["parse_error"])


class TestNoGroundTruthInJudgeCall(unittest.TestCase):
    def test_rendered_prompt_never_contains_a_ground_truth_risk_description(self):
        gt_path = judge.REPO_ROOT / "data" / "ground_truth" / f"{REAL_PROJECT}.json"
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        captured = {}
        fake_caller = lambda prompt: captured.setdefault("prompt", prompt) or VALID_JUDGE_JSON

        with tempfile.TemporaryDirectory() as td:
            raw_path = _write_raw_output(Path(td), "a.json")
            judge.judge_one(raw_path, fake_caller)

        for risk in gt["risks"]:
            desc = risk["description"].strip()
            if len(desc) < 40:
                continue
            self.assertNotIn(desc, captured["prompt"],
                             f"ground-truth risk text leaked into the judge prompt: {desc[:60]!r}")

    def test_judge_module_does_not_import_ground_truth_dir(self):
        # Static guard matching the module's own leakage claim in its docstring.
        self.assertFalse(hasattr(judge, "GROUND_TRUTH_DIR"))


class TestDefaultJudgeCallerUnpacksTheTuple(unittest.TestCase):
    """Regression test for the 2026-07-21 fix noted in judge.py: the wrapper
    used to `return call_fn(...)` directly, handing judge_one a raw
    (text, temperature_applied) 2-tuple instead of the text alone."""

    def test_call_fn_wrapper_returns_a_plain_string_not_a_tuple(self):
        fake_provider = lambda prompt, model_version, temperature, max_tokens: ("the judge's raw text", True)

        with mock.patch.dict("os.environ", {"JUDGE_MODEL_LABEL": "claude",
                                            "CLAUDE_MODEL_NAME": "claude-sonnet-5"}):
            import run_experiments as rx
            with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake_provider}):
                caller = judge._default_judge_caller()
                result = caller("any prompt")

        self.assertIsInstance(result, str)
        self.assertEqual(result, "the judge's raw text")

    def test_wrapper_output_is_directly_consumable_by_parse_judge_response(self):
        # End-to-end: if this ever regresses back to returning a tuple,
        # parse_judge_response's raw_text.strip() would raise AttributeError,
        # not just return an unexpected value - assert that doesn't happen.
        fake_provider = lambda prompt, model_version, temperature, max_tokens: (VALID_JUDGE_JSON, True)
        with mock.patch.dict("os.environ", {"JUDGE_MODEL_LABEL": "claude",
                                            "CLAUDE_MODEL_NAME": "claude-sonnet-5"}):
            import run_experiments as rx
            with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": fake_provider}):
                caller = judge._default_judge_caller()
                text = caller("any prompt")
        parsed, err = judge.parse_judge_response(text)   # must not raise
        self.assertIsNone(err)
        self.assertEqual(parsed["overall"], 4)

    def test_unknown_judge_model_label_is_rejected(self):
        with mock.patch.dict("os.environ", {"JUDGE_MODEL_LABEL": "not-a-real-model"}):
            with self.assertRaises(RuntimeError):
                judge._default_judge_caller()

    def test_defaults_to_claude_when_unset(self):
        with mock.patch.dict("os.environ", {"CLAUDE_MODEL_NAME": "claude-sonnet-5"}, clear=False):
            import os
            os.environ.pop("JUDGE_MODEL_LABEL", None)
            caller = judge._default_judge_caller()
        self.assertTrue(callable(caller))


class TestJudgeCLI(unittest.TestCase):
    def _run_main(self, argv, cwd_files_dir, out_dir):
        import sys as _sys
        with mock.patch.object(judge, "RAW_OUTPUTS_DIR", cwd_files_dir), \
             mock.patch.object(_sys, "argv", ["judge.py"] + argv), \
             mock.patch.object(judge, "_default_judge_caller", return_value=lambda p: VALID_JUDGE_JSON):
            judge.main()

    def test_all_flag_judges_every_raw_output_and_writes_judge_json(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            out_dir = Path(td) / "scored"
            raw_dir.mkdir()
            _write_raw_output(raw_dir, "a.json")
            _write_raw_output(raw_dir, "b.json")
            self._run_main(["--all", "--out-dir", str(out_dir)], raw_dir, out_dir)

            written = sorted(p.name for p in out_dir.glob("*.judge.json"))
        self.assertEqual(written, ["a.judge.json", "b.judge.json"])

    def test_gitkeep_is_excluded_from_all(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            out_dir = Path(td) / "scored"
            raw_dir.mkdir()
            (raw_dir / ".gitkeep").write_text("", encoding="utf-8")
            _write_raw_output(raw_dir, "a.json")
            self._run_main(["--all", "--out-dir", str(out_dir)], raw_dir, out_dir)
            written = list(out_dir.glob("*.judge.json"))
        self.assertEqual(len(written), 1)

    def test_no_targets_found_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            raw_dir.mkdir()
            with self.assertRaises(SystemExit) as cm:
                self._run_main(["--all", "--out-dir", str(Path(td) / "scored")], raw_dir, None)
        self.assertNotEqual(cm.exception.code, 0)

    def test_neither_all_nor_file_is_a_usage_error(self):
        import sys as _sys
        with mock.patch.object(_sys, "argv", ["judge.py"]):
            with self.assertRaises(SystemExit):
                judge.main()


if __name__ == "__main__":
    unittest.main()
