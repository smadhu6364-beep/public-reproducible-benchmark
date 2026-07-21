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


if __name__ == "__main__":
    unittest.main()
