"""Unit tests for model-response and judge-response parsing.

These parsers are the boundary between messy LLM text and the structured data
the whole pipeline depends on - and they are where a real bug already lived
(judge.py's bool-as-int: Python's bool is an int subclass, so {"completeness":
true} silently scored as 1). That regression is pinned here permanently.
Run: python -m unittest discover -s tests
"""

import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import run_experiments as rx  # noqa: E402
import judge  # noqa: E402


def _valid_register(project_id="P-TEST"):
    return {
        "project_id": project_id,
        "risks": [{
            "risk_id": "R01",
            "description": "A concrete risk.",
            "category": "schedule",
            "likelihood": 3,
            "impact": 4,
            "mitigation": "A concrete mitigation.",
            "evidence": "Section III.A: named delivery dependency.",
        }],
    }


class TestParseModelResponse(unittest.TestCase):
    def test_zero_shot_plain_json(self):
        parsed, err = rx.parse_model_response(json.dumps(_valid_register()), "zero_shot")
        self.assertIsNone(err)
        self.assertEqual(parsed["project_id"], "P-TEST")

    def test_zero_shot_markdown_fenced(self):
        text = "```json\n" + json.dumps(_valid_register()) + "\n```"
        parsed, err = rx.parse_model_response(text, "zero_shot")
        self.assertIsNone(err)
        self.assertEqual(len(parsed["risks"]), 1)

    def test_structured_requires_final_json_marker(self):
        body = json.dumps(_valid_register())
        good = "REASONING: I considered the delivery chain.\nFINAL JSON: " + body
        parsed, err = rx.parse_model_response(good, "structured")
        self.assertIsNone(err)
        self.assertEqual(parsed["project_id"], "P-TEST")

    def test_structured_without_marker_fails(self):
        parsed, err = rx.parse_model_response(json.dumps(_valid_register()), "structured")
        self.assertIsNone(parsed)
        self.assertIn("FINAL JSON", err)

    def test_schema_violation_rejected(self):
        bad = _valid_register()
        del bad["risks"][0]["evidence"]  # evidence is required in generation mode
        parsed, err = rx.parse_model_response(json.dumps(bad), "zero_shot")
        self.assertIsNone(parsed)
        self.assertIsNotNone(err)

    def test_category_other_rejected_for_generation(self):
        bad = _valid_register()
        bad["risks"][0]["category"] = "other"  # not in the generation enum
        parsed, err = rx.parse_model_response(json.dumps(bad), "zero_shot")
        self.assertIsNone(parsed)
        self.assertIsNotNone(err)

    def test_bare_json_with_surrounding_prose_fallback(self):
        text = "Here is the register you asked for:\n" + json.dumps(_valid_register()) + "\nHope that helps!"
        parsed, err = rx.parse_model_response(text, "zero_shot")
        self.assertIsNone(err)
        self.assertEqual(parsed["project_id"], "P-TEST")

    def test_structured_bare_array_instead_of_object(self):
        # Real observed behavior: model wraps FINAL JSON in a bare array
        # rather than the required {"project_id":..., "risks":[...]} object.
        risk = _valid_register()["risks"][0]
        text = "REASONING: ...\nFINAL JSON: [" + json.dumps(risk) + "]"
        parsed, err = rx.parse_model_response(text, "structured", expected_project_id="P-TEST")
        self.assertIsNone(err)
        self.assertEqual(parsed["project_id"], "P-TEST")
        self.assertEqual(len(parsed["risks"]), 1)

    def test_structured_bare_comma_separated_objects_no_wrapper(self):
        # Real observed behavior: model lists risk objects comma-separated
        # with no enclosing array at all after FINAL JSON:.
        r1 = _valid_register()["risks"][0]
        r2 = dict(r1, risk_id="R02", description="A second concrete risk.")
        text = "REASONING: ...\nFINAL JSON:\n" + json.dumps(r1) + ",\n" + json.dumps(r2)
        parsed, err = rx.parse_model_response(text, "structured", expected_project_id="P-TEST")
        self.assertIsNone(err)
        self.assertEqual(len(parsed["risks"]), 2)
        self.assertEqual(parsed["risks"][1]["risk_id"], "R02")

    def test_structured_trailing_prose_after_json_recovered(self):
        # Real observed behavior: explanatory prose appended after an
        # otherwise-complete JSON value breaks a strict end-of-string anchor.
        body = json.dumps(_valid_register(project_id="P-TEST"))
        text = "REASONING: ...\nFINAL JSON: " + body + "\n\nLet me know if you need anything else!"
        parsed, err = rx.parse_model_response(text, "structured")
        self.assertIsNone(err)
        self.assertEqual(parsed["project_id"], "P-TEST")

    def test_missing_project_id_backfilled_from_expected(self):
        reg = _valid_register()
        del reg["project_id"]
        parsed, err = rx.parse_model_response(json.dumps(reg), "zero_shot", expected_project_id="P-BACKFILLED")
        self.assertIsNone(err)
        self.assertEqual(parsed["project_id"], "P-BACKFILLED")

    def test_missing_project_id_without_expected_still_fails(self):
        reg = _valid_register()
        del reg["project_id"]
        parsed, err = rx.parse_model_response(json.dumps(reg), "zero_shot")
        self.assertIsNone(parsed)
        self.assertIn("project_id", err)

    def test_risk_register_key_normalized_to_risks(self):
        # Real observed behavior: model uses "risk_register" as the array
        # key instead of the schema's required "risks".
        reg = _valid_register()
        reg["risk_register"] = reg.pop("risks")
        parsed, err = rx.parse_model_response(json.dumps(reg), "zero_shot")
        self.assertIsNone(err)
        self.assertEqual(len(parsed["risks"]), 1)
        self.assertNotIn("risk_register", parsed)

    def test_category_case_mismatch_normalized(self):
        # Real observed behavior: model writes "External" (valid category,
        # wrong case) instead of the schema's required lowercase "external".
        reg = _valid_register()
        reg["risks"][0]["category"] = "Schedule"
        parsed, err = rx.parse_model_response(json.dumps(reg), "zero_shot")
        self.assertIsNone(err)
        self.assertEqual(parsed["risks"][0]["category"], "schedule")

    def test_invalid_category_still_rejected_not_papered_over(self):
        # Real observed model behavior (gpt/few_shot): inventing a category
        # outside the fixed taxonomy is a genuine finding, not a formatting
        # bug - must still fail, never silently remapped or accepted.
        reg = _valid_register()
        reg["risks"][0]["category"] = "legal"
        parsed, err = rx.parse_model_response(json.dumps(reg), "zero_shot", expected_project_id="P-TEST")
        self.assertIsNone(parsed)
        self.assertIn("legal", err)


class TestParseJudgeResponse(unittest.TestCase):
    def test_valid_scores(self):
        raw = json.dumps({"completeness": 4, "accuracy": 3, "actionability": 5, "overall": 4, "rationale": "ok"})
        parsed, err = judge.parse_judge_response(raw)
        self.assertIsNone(err)
        self.assertEqual(parsed["accuracy"], 3)

    def test_bool_as_int_rejected_regression(self):
        # THE regression test: bool is an int subclass; must NOT be accepted as a score.
        raw = json.dumps({"completeness": True, "accuracy": 3, "actionability": 5, "overall": 4})
        parsed, err = judge.parse_judge_response(raw)
        self.assertIsNone(parsed)
        self.assertIn("completeness", err)

    def test_missing_field_rejected(self):
        raw = json.dumps({"completeness": 4, "accuracy": 3, "actionability": 5})  # no 'overall'
        parsed, err = judge.parse_judge_response(raw)
        self.assertIsNone(parsed)
        self.assertIn("overall", err)

    def test_out_of_range_rejected(self):
        raw = json.dumps({"completeness": 6, "accuracy": 3, "actionability": 5, "overall": 4})
        parsed, err = judge.parse_judge_response(raw)
        self.assertIsNone(parsed)

    def test_float_score_rejected(self):
        raw = json.dumps({"completeness": 3.5, "accuracy": 3, "actionability": 5, "overall": 4})
        parsed, err = judge.parse_judge_response(raw)
        self.assertIsNone(parsed)

    def test_fenced_and_prose_wrapped_recovered(self):
        raw = "```json\n{\"completeness\": 4, \"accuracy\": 3, \"actionability\": 5, \"overall\": 4}\n```"
        parsed, err = judge.parse_judge_response(raw)
        self.assertIsNone(err)
        self.assertEqual(parsed["overall"], 4)


class TestNoGroundTruthInJudgePrompt(unittest.TestCase):
    def test_judge_prompt_contains_planning_and_register_only(self):
        prompt = judge.render_judge_prompt("PLANNING TEXT HERE", _valid_register())
        self.assertIn("PLANNING TEXT HERE", prompt)
        self.assertIn("R01", prompt)  # the generated register is included
        # sanity: the rubric never references a ground-truth/reference register
        self.assertNotIn("ground truth", prompt.lower())
        self.assertNotIn("ground-truth", prompt.lower())


class TestDefaultJudgeCallerReturnsTextNotTuple(unittest.TestCase):
    """Regression test for a real bug found 2026-07-21, same day it was
    introduced: call_claude/call_gpt/call_opensource in run_experiments.py
    were changed to return (text, temperature_applied) tuples (see
    call_gpt's docstring), but judge.py's _default_judge_caller()._call()
    still did `return call_fn(...)` directly - returning the raw tuple
    instead of just the text. judge_one() would pass that tuple straight
    into parse_judge_response(), whose first line is `raw_text.strip()` -
    an AttributeError on a tuple. Never exercised against a real API call
    (no keys have ever existed), so this would only have surfaced the first
    time `judge.py --all` actually ran for real. Caught by re-reading
    judge.py's own model-calling code as a direct follow-up to the
    call_gpt fix, not by any test - this test exists so it can't recur
    silently."""

    def _patched_dispatch(self, fake_call):
        from unittest import mock
        import os

        env_patch = mock.patch.dict(os.environ, {"CLAUDE_MODEL_NAME": "claude-sonnet-5", "JUDGE_MODEL_LABEL": "claude"})
        dispatch_patch = mock.patch.object(rx, "MODEL_DISPATCH", {"claude": fake_call, "gpt": fake_call, "opensource": fake_call})
        return env_patch, dispatch_patch

    def test_caller_returns_plain_string(self):
        def fake_call(prompt, model_version, temperature, max_tokens):
            return '{"completeness": 4, "accuracy": 3, "actionability": 5, "overall": 4}', True

        env_patch, dispatch_patch = self._patched_dispatch(fake_call)
        with env_patch, dispatch_patch:
            caller = judge._default_judge_caller()
            result = caller("some prompt")
        self.assertIsInstance(result, str)  # NOT a tuple - the actual regression
        # And the returned string must be directly usable by parse_judge_response,
        # exactly as judge_one() uses it.
        scores, err = judge.parse_judge_response(result)
        self.assertIsNone(err)
        self.assertEqual(scores["accuracy"], 3)

    def test_caller_handles_temperature_rejected_path(self):
        def fake_call(prompt, model_version, temperature, max_tokens):
            return '{"completeness": 2, "accuracy": 2, "actionability": 2, "overall": 2}', False

        env_patch, dispatch_patch = self._patched_dispatch(fake_call)
        with env_patch, dispatch_patch:
            caller = judge._default_judge_caller()
            result = caller("some prompt")  # must not raise, and must still be a plain string
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
