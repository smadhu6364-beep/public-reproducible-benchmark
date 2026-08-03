"""Unit tests for src/run_experiments.py's driver, guards, and cost estimator.

Everything here runs with the provider call STUBBED - no network, no API keys,
no spend. The point is that the first time run_one() executes end to end should
not be the first call of a 567-call, $60 grid: the append-only guarantee, the
reproducibility fields PROJECT_SPEC.md requires, the leakage guard, and the cost guard
should all be known-good before any money moves.

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
import run_experiments as rx  # noqa: E402

VALID_REGISTER = {
    "project_id": "P-UK-HyNetCCUSCluster",
    "risks": [{
        "risk_id": "R01",
        "description": "Cross-party consent delays hold up the pipeline corridor.",
        "category": "political_regulatory",
        "likelihood": 3,
        "impact": 4,
        "mitigation": "Sequence consent applications ahead of construction.",
        "evidence": "Planning doc, delivery-schedule section.",
    }],
}

REAL_PROJECT = "P-UK-HyNetCCUSCluster"


class _StubProvider:
    """Stands in for call_claude/call_gpt/call_opensource. Records the prompt
    it was handed so leakage can be asserted on the REAL prompt text."""

    def __init__(self, response_text=None, temperature_applied=True):
        self.response_text = response_text if response_text is not None else json.dumps(VALID_REGISTER)
        self.temperature_applied = temperature_applied
        self.calls = []

    def __call__(self, prompt, model_version, temperature, max_tokens):
        self.calls.append({"prompt": prompt, "model_version": model_version,
                           "temperature": temperature, "max_tokens": max_tokens})
        return self.response_text, self.temperature_applied


class _SandboxedRun:
    """Redirects run_one's writes into a temp tree. REPO_ROOT is patched too
    because run_one records out_path.relative_to(REPO_ROOT) in the run log."""

    def __init__(self, provider, model_label="claude"):
        self.provider = provider
        self.model_label = model_label

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        (root / "results").mkdir(parents=True, exist_ok=True)
        self._patches = [
            mock.patch.object(rx, "REPO_ROOT", root),
            mock.patch.object(rx, "RAW_OUTPUTS_DIR", root / "results" / "raw_outputs"),
            mock.patch.object(rx, "RUN_CONFIG_LOG", root / "results" / "run_config.jsonl"),
            mock.patch.dict(rx.MODEL_DISPATCH, {self.model_label: self.provider}),
            mock.patch.dict("os.environ", {
                "CLAUDE_MODEL_NAME": "claude-sonnet-5",
                "GPT_MODEL_NAME": "gpt-5.6-terra",
                "OPENSOURCE_MODEL_NAME": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            }),
        ]
        for p in self._patches:
            p.start()
        self.root = root
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        self._td.cleanup()
        return False

    def log_lines(self):
        log = self.root / "results" / "run_config.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestRunOneHappyPath(unittest.TestCase):
    def test_writes_record_with_every_reproducibility_field(self):
        # PROJECT_SPEC.md: "every run logs model version string, run date, temperature,
        # prompt file SHA256, into results/run_config.jsonl".
        provider = _StubProvider()
        with _SandboxedRun(provider) as sb:
            out = rx.run_one(REAL_PROJECT, "claude", "zero_shot", 1, 0.1, 4096)
            record = json.loads(out.read_text(encoding="utf-8"))
            logs = sb.log_lines()

        self.assertEqual(record["model_version"], "claude-sonnet-5")
        self.assertEqual(record["temperature"], 0.1)
        self.assertTrue(record["temperature_applied"])
        self.assertIsNone(record["parse_error"])
        self.assertEqual(record["parsed_risks"]["risks"][0]["risk_id"], "R01")
        self.assertRegex(record["prompt_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("run_date", record)

        self.assertEqual(len(logs), 1)
        for field in ("model_version", "run_date", "temperature", "prompt_sha256",
                      "raw_output_path", "parse_failed"):
            self.assertIn(field, logs[0])
        self.assertFalse(logs[0]["parse_failed"])

    def test_prompt_sha256_matches_the_prompt_file_on_disk(self):
        import hashlib
        expected = hashlib.sha256(rx.PROMPT_FILES["structured"].read_bytes()).hexdigest()
        self.assertEqual(rx.prompt_file_sha256("structured"), expected)

    def test_stub_received_the_configured_model_version_and_temperature(self):
        provider = _StubProvider()
        with _SandboxedRun(provider):
            rx.run_one(REAL_PROJECT, "claude", "few_shot", 1, 0.0, 2048)
        self.assertEqual(provider.calls[0]["model_version"], "claude-sonnet-5")
        self.assertEqual(provider.calls[0]["temperature"], 0.0)
        self.assertEqual(provider.calls[0]["max_tokens"], 2048)

    def test_parse_failure_is_recorded_not_raised(self):
        # A model returning prose instead of JSON is data, not a crash.
        provider = _StubProvider(response_text="I'm afraid I can't do that.")
        with _SandboxedRun(provider) as sb:
            out = rx.run_one(REAL_PROJECT, "claude", "zero_shot", 1, 0.1, 4096)
            record = json.loads(out.read_text(encoding="utf-8"))
            logs = sb.log_lines()
        self.assertIsNone(record["parsed_risks"])
        self.assertIsNotNone(record["parse_error"])
        self.assertTrue(logs[0]["parse_failed"])
        self.assertIn("can't do that", record["raw_response_text"])  # raw text always kept

    def test_temperature_not_applied_is_recorded(self):
        # call_gpt falls back to the provider default if temperature is refused;
        # the record must not claim 0.1 was used when it wasn't.
        provider = _StubProvider(temperature_applied=False)
        with _SandboxedRun(provider) as sb:
            out = rx.run_one(REAL_PROJECT, "claude", "zero_shot", 1, 0.1, 4096)
            record = json.loads(out.read_text(encoding="utf-8"))
            logs = sb.log_lines()
        self.assertFalse(record["temperature_applied"])
        self.assertFalse(logs[0]["temperature_applied"])


class TestAppendOnly(unittest.TestCase):
    def test_rerunning_the_same_run_index_refuses_to_overwrite(self):
        provider = _StubProvider()
        with _SandboxedRun(provider):
            rx.run_one(REAL_PROJECT, "claude", "zero_shot", 1, 0.1, 4096)
            with self.assertRaises(FileExistsError):
                rx.run_one(REAL_PROJECT, "claude", "zero_shot", 1, 0.1, 4096)

    def test_next_free_run_index_accumulates_runs(self):
        provider = _StubProvider()
        with _SandboxedRun(provider):
            self.assertEqual(rx.next_free_run_index(REAL_PROJECT, "claude", "zero_shot"), 1)
            rx.run_one(REAL_PROJECT, "claude", "zero_shot", 1, 0.1, 4096)
            self.assertEqual(rx.next_free_run_index(REAL_PROJECT, "claude", "zero_shot"), 2)
            rx.run_one(REAL_PROJECT, "claude", "zero_shot", 2, 0.1, 4096)
            self.assertEqual(rx.next_free_run_index(REAL_PROJECT, "claude", "zero_shot"), 3)
            # A different cell is tracked independently.
            self.assertEqual(rx.next_free_run_index(REAL_PROJECT, "claude", "few_shot"), 1)

    def test_raw_output_filename_round_trips_through_match_parser(self):
        # match.py rediscovers (project, model, prompt, run) from the filename;
        # the two conventions must not drift apart.
        import match
        p = rx.raw_output_path("P-SRB-CompetitivenessJobs", "opensource", "structured", 3)
        parsed = match.parse_raw_output_filename(p)
        self.assertEqual(parsed, {"project_id": "P-SRB-CompetitivenessJobs",
                                  "model": "opensource", "prompt": "structured", "run": 3})


class TestLeakageGuard(unittest.TestCase):
    def test_real_corpus_passes_the_guard(self):
        rx.assert_no_ground_truth_leakage()  # must not raise on the shipped prompts

    def test_guard_trips_if_few_shot_names_a_real_corpus_project(self):
        with tempfile.TemporaryDirectory() as td:
            poisoned = Path(td) / "few_shot.txt"
            poisoned.write_text(
                "Here is an example from P-UK-HyNetCCUSCluster: ...", encoding="utf-8")
            with mock.patch.dict(rx.PROMPT_FILES, {"few_shot": poisoned}):
                with self.assertRaises(RuntimeError) as cm:
                    rx.assert_no_ground_truth_leakage()
        self.assertIn("LEAKAGE GUARD TRIPPED", str(cm.exception))

    def test_rendered_prompt_contains_planning_text_only(self):
        # The strongest available check: the actual prompt a model receives must
        # not contain the ground-truth register's risk descriptions.
        gt_path = rx.GROUND_TRUTH_DIR / f"{REAL_PROJECT}.json"
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        prompt = rx.render_prompt("zero_shot", REAL_PROJECT)
        for risk in gt["risks"]:
            desc = risk["description"].strip()
            if len(desc) < 40:
                continue  # too short to be a meaningful containment test
            self.assertNotIn(desc, prompt,
                             f"ground-truth risk text leaked into the prompt: {desc[:60]!r}")

    def test_no_placeholder_left_unfilled(self):
        prompt = rx.render_prompt("structured", REAL_PROJECT)
        self.assertNotIn("{{PLANNING_DOCUMENT}}", prompt)
        self.assertNotIn("{{PROJECT_ID}}", prompt)


class TestGridComposition(unittest.TestCase):
    def test_default_grid_is_the_included_corpus_only(self):
        ids = rx.all_project_ids()
        self.assertNotIn("P-REGION-AIM4Learning", ids)   # set aside
        self.assertNotIn("P-UK-SizewellC", ids)          # excluded
        self.assertNotIn("P-UK-ConnectToWork", ids)      # excluded
        self.assertEqual(len(ids), len(set(ids)))

    def test_grid_size_is_projects_times_nine(self):
        n = len(rx.all_project_ids())
        self.assertEqual(n * len(rx.MODEL_DISPATCH) * len(rx.PROMPT_FILES), n * 9)


class TestCostEstimator(unittest.TestCase):
    def _cells(self, n_projects=1):
        ids = rx.all_project_ids()[:n_projects]
        return [rx.GridCell(p, m, pr) for p in ids
                for m in rx.MODEL_DISPATCH for pr in rx.PROMPT_FILES]

    def test_cost_scales_linearly_with_runs(self):
        env = {"CLAUDE_MODEL_NAME": "claude-sonnet-5", "GPT_MODEL_NAME": "gpt-5.6-terra",
               "OPENSOURCE_MODEL_NAME": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
               "OPENSOURCE_PRICE_INPUT_PER_MTOK": "1.04",
               "OPENSOURCE_PRICE_OUTPUT_PER_MTOK": "1.04"}
        with mock.patch.dict("os.environ", env):
            one = rx.estimate_cost(self._cells(2), 1, 4096)
            three = rx.estimate_cost(self._cells(2), 3, 4096)
        self.assertAlmostEqual(three["estimated_total_usd"], one["estimated_total_usd"] * 3, places=1)

    def test_unpriced_model_is_reported_not_silently_zero(self):
        # The dangerous failure is a $0 estimate that looks like "free".
        with mock.patch.dict("os.environ", {"CLAUDE_MODEL_NAME": "some-unreleased-model",
                                            "GPT_MODEL_NAME": "gpt-5.6-terra",
                                            "OPENSOURCE_MODEL_NAME": "x"}, clear=False):
            est = rx.estimate_cost(self._cells(1), 1, 4096)
        self.assertIn("some-unreleased-model", est["models_missing_pricing_data"])

    def test_opensource_price_falls_back_to_env(self):
        with mock.patch.dict("os.environ", {
                "CLAUDE_MODEL_NAME": "claude-sonnet-5", "GPT_MODEL_NAME": "gpt-5.6-terra",
                "OPENSOURCE_MODEL_NAME": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "OPENSOURCE_PRICE_INPUT_PER_MTOK": "1.04",
                "OPENSOURCE_PRICE_OUTPUT_PER_MTOK": "1.04"}):
            est = rx.estimate_cost(self._cells(1), 1, 4096)
        self.assertEqual(est["models_missing_pricing_data"], [])
        self.assertGreater(est["by_model"]["opensource"]["estimated_usd"], 0)

    def test_cost_guard_threshold_is_the_documented_thirty_dollars(self):
        self.assertEqual(rx.COST_GUARD_THRESHOLD_USD, 30.0)

    def test_default_temperature_within_claudemd_range(self):
        self.assertGreaterEqual(rx.DEFAULT_TEMPERATURE, 0.0)
        self.assertLessEqual(rx.DEFAULT_TEMPERATURE, 0.2)


if __name__ == "__main__":
    unittest.main()
