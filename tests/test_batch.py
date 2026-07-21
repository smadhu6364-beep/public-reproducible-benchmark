"""Unit tests for run_experiments.py's Batch API support (--batch / --batch-check).

Everything here runs against HAND-BUILT FAKE anthropic/openai modules injected
via sys.modules - no real network, no API keys, no spend, and no dependency on
whatever version of the real SDKs happens to be installed in this environment.
The fakes match the real SDK shapes confirmed 2026-07-21 via inspect.signature()
and direct source reads against the actually-installed anthropic==0.117.0 /
openai==1.109.1 (see run_experiments.py's module docstring for exactly what was
checked). This is the same "verify the mock against the real SDK before trusting
the test" discipline call_gpt's temperature-retry path got - it caught nothing
wrong there, but the point is finding out BEFORE a real key exists, not after.

If a real batch submit/check cycle ever runs for real, cross-check
results/batch_jobs.json and the first few batch-sourced raw_outputs records by
hand - these fakes have never been exercised against a live provider.

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import run_experiments as rx  # noqa: E402

REAL_PROJECTS = rx.all_project_ids()[:2]  # two real, real corpus project ids


class _SandboxedBatch:
    """Like test_run_pipeline.py's _SandboxedRun, extended to also isolate
    BATCH_JOBS_LOG so these tests never touch the real results/ directory.
    PROCESSED_DIR/GROUND_TRUTH_DIR/PROMPTS_DIR/MANIFEST_PATH are deliberately
    left pointed at the real repo (same choice test_run_pipeline.py makes) so
    render_prompt() still produces a real, meaningful prompt."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        (root / "results").mkdir(parents=True, exist_ok=True)
        self._patches = [
            mock.patch.object(rx, "REPO_ROOT", root),
            mock.patch.object(rx, "RAW_OUTPUTS_DIR", root / "results" / "raw_outputs"),
            mock.patch.object(rx, "RUN_CONFIG_LOG", root / "results" / "run_config.jsonl"),
            mock.patch.object(rx, "BATCH_JOBS_LOG", root / "results" / "batch_jobs.json"),
            mock.patch.dict("os.environ", {
                "CLAUDE_MODEL_NAME": "claude-sonnet-5",
                "GPT_MODEL_NAME": "gpt-5.6-terra",
                "OPENSOURCE_MODEL_NAME": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                # Fake keys: _require_env only checks presence, and the fake
                # anthropic/openai modules injected via sys.modules never
                # actually send them anywhere. Real keys are never used here.
                "ANTHROPIC_API_KEY": "sk-ant-fake-not-real",
                "OPENAI_API_KEY": "sk-fake-not-real",
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


# --- Fake anthropic SDK, shaped like the real anthropic==0.117.0 batches surface ---

class _FakeAnthropicBatchesAPI:
    def __init__(self):
        self.create_calls = []
        self.retrieve_calls = []
        self.results_calls = []
        self.next_batch_id = "msgbatch_fake001"
        self.retrieve_response = None
        self.results_response = []

    def create(self, requests):
        self.create_calls.append(requests)
        return SimpleNamespace(id=self.next_batch_id, processing_status="in_progress")

    def retrieve(self, batch_id):
        self.retrieve_calls.append(batch_id)
        return self.retrieve_response

    def results(self, batch_id):
        self.results_calls.append(batch_id)
        return iter(self.results_response)


def _fake_anthropic_module(batches_api):
    messages = SimpleNamespace(batches=batches_api)
    holder = SimpleNamespace(instances=[])

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.messages = messages
            holder.instances.append(self)

    class BadRequestError(Exception):
        pass

    return SimpleNamespace(Anthropic=FakeAnthropic, BadRequestError=BadRequestError), holder


# --- Fake openai SDK, shaped like the real openai==1.109.1 files/batches surface ---

class _FakeOpenAIFilesAPI:
    def __init__(self):
        self.create_calls = []
        self.content_calls = []
        self.next_file_id = "file-fake001"
        self.content_response_text = ""

    def create(self, file, purpose):
        self.create_calls.append({"file": file, "purpose": purpose})
        return SimpleNamespace(id=self.next_file_id)

    def content(self, file_id):
        self.content_calls.append(file_id)
        return SimpleNamespace(text=self.content_response_text)


class _FakeOpenAIBatchesAPI:
    def __init__(self):
        self.create_calls = []
        self.retrieve_calls = []
        self.next_batch_id = "batch_fake001"
        self.retrieve_response = None

    def create(self, input_file_id, endpoint, completion_window):
        self.create_calls.append({
            "input_file_id": input_file_id, "endpoint": endpoint,
            "completion_window": completion_window,
        })
        return SimpleNamespace(id=self.next_batch_id, status="validating")

    def retrieve(self, batch_id):
        self.retrieve_calls.append(batch_id)
        return self.retrieve_response


def _fake_openai_module(files_api, batches_api):
    class FakeOpenAI:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.files = files_api
            self.batches = batches_api

    class BadRequestError(Exception):
        pass

    return SimpleNamespace(OpenAI=FakeOpenAI, BadRequestError=BadRequestError)


class TestBatchEligibleLabels(unittest.TestCase):
    def test_claude_and_gpt_only(self):
        self.assertEqual(rx.BATCH_ELIGIBLE_LABELS, frozenset({"claude", "gpt"}))

    def test_opensource_is_never_batch_eligible(self):
        # Together AI's batch-discount availability was never verified - the
        # whole reason this slot always runs synchronously. If this ever
        # changes it must be a deliberate edit, not a silent scope creep.
        self.assertNotIn("opensource", rx.BATCH_ELIGIBLE_LABELS)


class TestBuildBatchUnits(unittest.TestCase):
    def test_assigns_sequential_run_index_per_cell(self):
        with _SandboxedBatch():
            cells = [rx.GridCell(REAL_PROJECTS[0], "claude", "zero_shot")]
            units = rx.build_batch_units(cells, 2, "claude")
        self.assertEqual([u["run_index"] for u in units], [1, 2])
        self.assertTrue(all(u["model_label"] == "claude" for u in units))

    def test_filters_to_the_requested_label_only(self):
        with _SandboxedBatch():
            cells = [rx.GridCell(REAL_PROJECTS[0], "claude", "zero_shot"),
                     rx.GridCell(REAL_PROJECTS[0], "gpt", "zero_shot"),
                     rx.GridCell(REAL_PROJECTS[0], "opensource", "zero_shot")]
            units = rx.build_batch_units(cells, 1, "gpt")
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["model_label"], "gpt")

    def test_starts_after_runs_already_on_disk(self):
        # A prior synchronous run(s) for this combo must not be collided with.
        with _SandboxedBatch():
            provider = lambda *a, **k: (json.dumps({"project_id": REAL_PROJECTS[0], "risks": []}), True)
            with mock.patch.dict(rx.MODEL_DISPATCH, {"claude": provider}):
                rx.run_one(REAL_PROJECTS[0], "claude", "zero_shot", 1, 0.1, 4096)
            units = rx.build_batch_units([rx.GridCell(REAL_PROJECTS[0], "claude", "zero_shot")], 2, "claude")
        self.assertEqual([u["run_index"] for u in units], [2, 3])


class TestBatchCustomId(unittest.TestCase):
    def test_format(self):
        self.assertEqual(rx._batch_custom_id("claude", 0), "req-claude-00000")
        self.assertEqual(rx._batch_custom_id("gpt", 41), "req-gpt-00041")

    def test_stays_well_under_anthropics_length_limit(self):
        # The whole point of NOT encoding project_id: real ids like
        # 'P-MAR-SecondIdentityTargetingSocialProtection' (47 chars) combined
        # with a '__model__prompt__runN' suffix risk the ~64-char ceiling.
        self.assertLessEqual(len(rx._batch_custom_id("claude", 99999)), 64)


class TestSubmitClaudeBatch(unittest.TestCase):
    def test_sends_correct_request_shape(self):
        batches_api = _FakeAnthropicBatchesAPI()
        fake_mod, _ = _fake_anthropic_module(batches_api)
        with _SandboxedBatch():
            units = [{"project_id": REAL_PROJECTS[0], "model_label": "claude",
                      "prompt_strategy": "zero_shot", "run_index": 1, "custom_id": "req-claude-00000"}]
            with mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
                batch_id = rx.submit_claude_batch(units, "claude-sonnet-5", 0.1, 4096)

        self.assertEqual(batch_id, "msgbatch_fake001")
        self.assertEqual(len(batches_api.create_calls), 1)
        req = batches_api.create_calls[0][0]
        self.assertEqual(req["custom_id"], "req-claude-00000")
        self.assertEqual(req["params"]["model"], "claude-sonnet-5")
        self.assertEqual(req["params"]["max_tokens"], 4096)
        self.assertEqual(req["params"]["temperature"], 0.1)
        self.assertEqual(req["params"]["messages"][0]["role"], "user")
        self.assertIn(REAL_PROJECTS[0], req["params"]["messages"][0]["content"])


class TestSubmitGptBatch(unittest.TestCase):
    def test_uploads_correct_jsonl_and_creates_batch(self):
        files_api = _FakeOpenAIFilesAPI()
        batches_api = _FakeOpenAIBatchesAPI()
        fake_mod = _fake_openai_module(files_api, batches_api)
        with _SandboxedBatch():
            units = [{"project_id": REAL_PROJECTS[0], "model_label": "gpt",
                      "prompt_strategy": "zero_shot", "run_index": 1, "custom_id": "req-gpt-00000"}]
            with mock.patch.dict(sys.modules, {"openai": fake_mod}):
                batch_id = rx.submit_gpt_batch(units, "gpt-5.6-terra", 0.1, 4096)

        self.assertEqual(batch_id, "batch_fake001")
        uploaded_bytes = files_api.create_calls[0]["file"][1]
        row = json.loads(uploaded_bytes.decode("utf-8").strip().splitlines()[0])
        self.assertEqual(row["custom_id"], "req-gpt-00000")
        self.assertEqual(row["url"], "/v1/chat/completions")
        self.assertEqual(row["body"]["model"], "gpt-5.6-terra")
        self.assertEqual(row["body"]["max_completion_tokens"], 4096)
        self.assertNotIn("max_tokens", row["body"])  # legacy param must not appear - see call_gpt's finding
        self.assertEqual(row["body"]["temperature"], 0.1)
        self.assertEqual(batches_api.create_calls[0]["input_file_id"], "file-fake001")
        self.assertEqual(batches_api.create_calls[0]["completion_window"], "24h")


class TestSubmitBatchGrid(unittest.TestCase):
    def test_submits_claude_and_gpt_but_never_opensource(self):
        claude_batches = _FakeAnthropicBatchesAPI()
        anthropic_mod, _ = _fake_anthropic_module(claude_batches)
        gpt_files, gpt_batches = _FakeOpenAIFilesAPI(), _FakeOpenAIBatchesAPI()
        openai_mod = _fake_openai_module(gpt_files, gpt_batches)

        with _SandboxedBatch() as sb:
            cells = [rx.GridCell(REAL_PROJECTS[0], m, "zero_shot") for m in ("claude", "gpt", "opensource")]
            with mock.patch.dict(sys.modules, {"anthropic": anthropic_mod, "openai": openai_mod}):
                result = rx.submit_batch_grid(cells, 1, 0.1, 4096)
            jobs = json.loads((sb.root / "results" / "batch_jobs.json").read_text())

        self.assertEqual({s["provider"] for s in result["submitted"]}, {"anthropic", "openai"})
        self.assertEqual(len(jobs), 2)
        self.assertTrue(all(j["status"] == "submitted" for j in jobs))
        self.assertEqual(len(claude_batches.create_calls), 1)
        self.assertEqual(len(gpt_batches.create_calls), 1)

    def test_only_submits_for_labels_actually_present_in_cells(self):
        claude_batches = _FakeAnthropicBatchesAPI()
        anthropic_mod, _ = _fake_anthropic_module(claude_batches)
        with _SandboxedBatch():
            cells = [rx.GridCell(REAL_PROJECTS[0], "claude", "zero_shot")]  # no gpt cells
            with mock.patch.dict(sys.modules, {"anthropic": anthropic_mod}):
                result = rx.submit_batch_grid(cells, 1, 0.1, 4096)
        self.assertEqual(len(result["submitted"]), 1)
        self.assertEqual(result["submitted"][0]["provider"], "anthropic")

    def test_appends_to_existing_log_rather_than_clobbering(self):
        claude_batches = _FakeAnthropicBatchesAPI()
        anthropic_mod, _ = _fake_anthropic_module(claude_batches)
        with _SandboxedBatch() as sb:
            cells = [rx.GridCell(REAL_PROJECTS[0], "claude", "zero_shot")]
            with mock.patch.dict(sys.modules, {"anthropic": anthropic_mod}):
                rx.submit_batch_grid(cells, 1, 0.1, 4096)
                claude_batches.next_batch_id = "msgbatch_fake002"
                rx.submit_batch_grid(cells, 1, 0.1, 4096)
            jobs = json.loads((sb.root / "results" / "batch_jobs.json").read_text())
        self.assertEqual({j["batch_id"] for j in jobs}, {"msgbatch_fake001", "msgbatch_fake002"})


class TestCheckClaudeBatch(unittest.TestCase):
    def test_not_ended_returns_status_and_no_results(self):
        batches_api = _FakeAnthropicBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(processing_status="in_progress")
        fake_mod, _ = _fake_anthropic_module(batches_api)
        with _SandboxedBatch():
            with mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
                status, results = rx._check_claude_batch("msgbatch_fake001")
        self.assertEqual(status, "in_progress")
        self.assertEqual(results, [])

    def test_ended_parses_succeeded_and_errored_rows(self):
        batches_api = _FakeAnthropicBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(processing_status="ended")
        ok_block = SimpleNamespace(type="text", text='{"risks": []}')
        batches_api.results_response = [
            SimpleNamespace(custom_id="req-claude-00000",
                             result=SimpleNamespace(type="succeeded", message=SimpleNamespace(content=[ok_block]))),
            SimpleNamespace(custom_id="req-claude-00001",
                             result=SimpleNamespace(type="errored", error=SimpleNamespace(message="overloaded"))),
        ]
        fake_mod, _ = _fake_anthropic_module(batches_api)
        with _SandboxedBatch():
            with mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
                status, results = rx._check_claude_batch("msgbatch_fake001")
        self.assertEqual(status, "ended")
        self.assertEqual(results, [
            ("req-claude-00000", '{"risks": []}', True),
            ("req-claude-00001", None, False),
        ])


class TestCheckGptBatch(unittest.TestCase):
    def test_not_completed_returns_status_and_no_results(self):
        batches_api = _FakeOpenAIBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(status="in_progress")
        fake_mod = _fake_openai_module(_FakeOpenAIFilesAPI(), batches_api)
        with _SandboxedBatch():
            with mock.patch.dict(sys.modules, {"openai": fake_mod}):
                status, results = rx._check_gpt_batch("batch_fake001")
        self.assertEqual(status, "in_progress")
        self.assertEqual(results, [])

    def test_completed_parses_success_and_error_rows(self):
        files_api = _FakeOpenAIFilesAPI()
        ok_row = {"custom_id": "req-gpt-00000", "response": {"status_code": 200,
                  "body": {"choices": [{"message": {"content": '{"risks": []}'}}]}}, "error": None}
        err_row = {"custom_id": "req-gpt-00001", "response": None,
                   "error": {"code": "server_error", "message": "boom"}}
        files_api.content_response_text = json.dumps(ok_row) + "\n" + json.dumps(err_row) + "\n"
        batches_api = _FakeOpenAIBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(status="completed", output_file_id="file-out1", error_file_id=None)
        fake_mod = _fake_openai_module(files_api, batches_api)

        with _SandboxedBatch():
            with mock.patch.dict(sys.modules, {"openai": fake_mod}):
                status, results = rx._check_gpt_batch("batch_fake001")

        self.assertEqual(status, "completed")
        self.assertEqual(results, [
            ("req-gpt-00000", '{"risks": []}', True),
            ("req-gpt-00001", None, False),
        ])
        self.assertEqual(files_api.content_calls, ["file-out1"])

    def test_temperature_related_error_still_fails_cleanly_not_silently(self):
        # No defensive retry at the batch layer (see submit_gpt_batch's
        # docstring) - a temperature rejection must show up as a clean,
        # visible failure, never a silently-dropped or silently-altered run.
        files_api = _FakeOpenAIFilesAPI()
        err_row = {"custom_id": "req-gpt-00000", "response": None,
                   "error": {"code": "invalid_request", "message": "temperature is not supported with this model"}}
        files_api.content_response_text = json.dumps(err_row) + "\n"
        batches_api = _FakeOpenAIBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(status="completed", output_file_id="file-out1", error_file_id=None)
        fake_mod = _fake_openai_module(files_api, batches_api)
        with _SandboxedBatch():
            with mock.patch.dict(sys.modules, {"openai": fake_mod}):
                status, results = rx._check_gpt_batch("batch_fake001")
        self.assertEqual(results, [("req-gpt-00000", None, False)])


class TestCheckAndCollectBatches(unittest.TestCase):
    def test_no_jobs_file_reports_nothing_to_check(self):
        with _SandboxedBatch():
            result = rx.check_and_collect_batches()
        self.assertEqual(result["jobs"], [])

    def test_collects_finished_job_and_writes_records_identical_in_shape_to_a_sync_run(self):
        batches_api = _FakeAnthropicBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(processing_status="ended")
        # output_schema.json requires project_id (risks: [] alone is invalid -
        # "additionalProperties": false + required: ["project_id", "risks"]).
        ok_block = SimpleNamespace(type="text", text=json.dumps({"project_id": REAL_PROJECTS[0], "risks": []}))
        batches_api.results_response = [
            SimpleNamespace(custom_id="req-claude-00000",
                             result=SimpleNamespace(type="succeeded", message=SimpleNamespace(content=[ok_block]))),
        ]
        fake_mod, _ = _fake_anthropic_module(batches_api)

        with _SandboxedBatch() as sb:
            jobs = [{
                "batch_id": "msgbatch_fake001", "provider": "anthropic", "model_label": "claude",
                "model_version": "claude-sonnet-5", "temperature": 0.1, "max_tokens": 4096,
                "submitted_at": "2026-07-21T00:00:00+00:00", "status": "submitted",
                "units": [{"project_id": REAL_PROJECTS[0], "model_label": "claude",
                           "prompt_strategy": "zero_shot", "run_index": 1, "custom_id": "req-claude-00000"}],
            }]
            (sb.root / "results" / "batch_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")

            with mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
                result = rx.check_and_collect_batches()

            out_path = rx.raw_output_path(REAL_PROJECTS[0], "claude", "zero_shot", 1)
            record = json.loads(out_path.read_text(encoding="utf-8"))
            log_lines = [json.loads(l) for l in (sb.root / "results" / "run_config.jsonl").read_text().splitlines()]
            saved_jobs = json.loads((sb.root / "results" / "batch_jobs.json").read_text())

        self.assertEqual(result["jobs"][0]["status"], "collected")
        self.assertEqual(result["jobs"][0]["n_ok"], 1)
        # Same fields CLAUDE.md requires from a synchronous run - a reader of
        # run_config.jsonl or raw_outputs cannot tell this came from a batch.
        self.assertEqual(record["model_version"], "claude-sonnet-5")
        self.assertTrue(record["temperature_applied"])
        self.assertEqual(record["parsed_risks"], {"project_id": REAL_PROJECTS[0], "risks": []})
        self.assertRegex(record["prompt_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(log_lines), 1)
        self.assertFalse(log_lines[0]["parse_failed"])
        self.assertEqual(saved_jobs[0]["status"], "collected")

    def test_already_collected_jobs_are_skipped_not_reprocessed(self):
        with _SandboxedBatch() as sb:
            jobs = [{"batch_id": "x", "provider": "anthropic", "status": "collected", "units": []}]
            (sb.root / "results" / "batch_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            result = rx.check_and_collect_batches()
        self.assertEqual(result["jobs"][0]["status"], "already collected")

    def test_pending_job_reports_status_and_writes_nothing(self):
        batches_api = _FakeAnthropicBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(processing_status="in_progress")
        fake_mod, _ = _fake_anthropic_module(batches_api)
        with _SandboxedBatch() as sb:
            jobs = [{"batch_id": "msgbatch_fake001", "provider": "anthropic", "model_label": "claude",
                     "model_version": "claude-sonnet-5", "temperature": 0.1, "max_tokens": 4096,
                     "submitted_at": "x", "status": "submitted", "units": []}]
            (sb.root / "results" / "batch_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            with mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
                result = rx.check_and_collect_batches()
            self.assertFalse((sb.root / "results" / "raw_outputs").exists())
        self.assertEqual(result["jobs"][0]["status"], "in_progress")

    def test_failed_row_is_counted_and_never_written(self):
        batches_api = _FakeAnthropicBatchesAPI()
        batches_api.retrieve_response = SimpleNamespace(processing_status="ended")
        batches_api.results_response = [
            SimpleNamespace(custom_id="req-claude-00000",
                             result=SimpleNamespace(type="errored", error=SimpleNamespace(message="boom"))),
        ]
        fake_mod, _ = _fake_anthropic_module(batches_api)
        with _SandboxedBatch() as sb:
            jobs = [{"batch_id": "msgbatch_fake001", "provider": "anthropic", "model_label": "claude",
                     "model_version": "claude-sonnet-5", "temperature": 0.1, "max_tokens": 4096,
                     "submitted_at": "x", "status": "submitted",
                     "units": [{"project_id": REAL_PROJECTS[0], "model_label": "claude",
                                "prompt_strategy": "zero_shot", "run_index": 1, "custom_id": "req-claude-00000"}]}]
            (sb.root / "results" / "batch_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            with mock.patch.dict(sys.modules, {"anthropic": fake_mod}):
                result = rx.check_and_collect_batches()
            self.assertFalse(rx.raw_output_path(REAL_PROJECTS[0], "claude", "zero_shot", 1).exists())
        self.assertEqual(result["jobs"][0]["n_failed"], 1)
        self.assertEqual(result["jobs"][0]["n_ok"], 0)


class TestEstimateCostBatchDiscount(unittest.TestCase):
    _ENV = {
        "CLAUDE_MODEL_NAME": "claude-sonnet-5", "GPT_MODEL_NAME": "gpt-5.6-terra",
        "OPENSOURCE_MODEL_NAME": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "OPENSOURCE_PRICE_INPUT_PER_MTOK": "1.04", "OPENSOURCE_PRICE_OUTPUT_PER_MTOK": "1.04",
    }

    def _cells(self, n=2):
        ids = rx.all_project_ids()[:n]
        return [rx.GridCell(p, m, pr) for p in ids for m in rx.MODEL_DISPATCH for pr in rx.PROMPT_FILES]

    def test_batch_eligible_labels_get_half_price_others_unaffected(self):
        with mock.patch.dict("os.environ", self._ENV):
            cells = self._cells(2)
            sync = rx.estimate_cost(cells, 1, 4096)
            batch = rx.estimate_cost(cells, 1, 4096, batch_labels=rx.BATCH_ELIGIBLE_LABELS)

        # places=1 (not 2): both sides are independently rounded to the cent
        # by estimate_cost() - sync rounds its full total then we halve it in
        # the assertion, batch halves the per-MTok rate then rounds its own
        # total - two different rounding paths that can legitimately differ
        # by a cent at n_cells > 1. The invariant under test is "roughly
        # half", which places=1 (within 5 cents) checks without being a false
        # positive on harmless double-rounding.
        self.assertAlmostEqual(batch["by_model"]["claude"]["estimated_usd"],
                                sync["by_model"]["claude"]["estimated_usd"] / 2, places=1)
        self.assertAlmostEqual(batch["by_model"]["gpt"]["estimated_usd"],
                                sync["by_model"]["gpt"]["estimated_usd"] / 2, places=1)
        self.assertAlmostEqual(batch["by_model"]["opensource"]["estimated_usd"],
                                sync["by_model"]["opensource"]["estimated_usd"], places=2)
        self.assertEqual(batch["batch_discounted_labels"], ["claude", "gpt"])

    def test_real_full_grid_two_runs_batched_clears_the_cost_guard(self):
        # This is the actual claim the feature exists to satisfy - verify it
        # against the REAL corpus and REAL pricing config, not a toy fixture.
        with mock.patch.dict("os.environ", self._ENV):
            cells = self._cells(len(rx.all_project_ids()))
            estimate = rx.estimate_cost(cells, 2, 4096, batch_labels=rx.BATCH_ELIGIBLE_LABELS)
        self.assertLess(estimate["estimated_total_usd"], rx.COST_GUARD_THRESHOLD_USD)


class TestBatchCLIFlags(unittest.TestCase):
    def test_batch_and_batch_check_are_mutually_exclusive(self):
        with _SandboxedBatch():
            with mock.patch.object(sys, "argv", ["run_experiments.py", "--batch", "--batch-check"]):
                with self.assertRaises(SystemExit) as cm:
                    rx.main()
        self.assertEqual(cm.exception.code, 2)

    def test_batch_check_alone_short_circuits_cleanly_with_no_jobs(self):
        with _SandboxedBatch():
            with mock.patch.object(sys, "argv", ["run_experiments.py", "--batch-check"]):
                rx.main()  # must not raise / must not sys.exit

    def test_batch_flag_submits_claude_and_gpt_and_still_runs_opensource_synchronously(self):
        claude_batches = _FakeAnthropicBatchesAPI()
        anthropic_mod, _ = _fake_anthropic_module(claude_batches)
        gpt_files, gpt_batches = _FakeOpenAIFilesAPI(), _FakeOpenAIBatchesAPI()
        openai_mod = _fake_openai_module(gpt_files, gpt_batches)
        opensource_provider = lambda *a, **k: (json.dumps({"project_id": REAL_PROJECTS[0], "risks": []}), True)

        with _SandboxedBatch() as sb:
            argv = ["run_experiments.py", "--project", REAL_PROJECTS[0], "--model", "claude",
                    "--model", "gpt", "--model", "opensource", "--prompt", "zero_shot",
                    "--runs", "1", "--batch", "--confirm-cost"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.dict(sys.modules, {"anthropic": anthropic_mod, "openai": openai_mod}), \
                 mock.patch.dict(rx.MODEL_DISPATCH, {"opensource": opensource_provider}):
                rx.main()

            jobs = json.loads((sb.root / "results" / "batch_jobs.json").read_text())
            opensource_out = rx.raw_output_path(REAL_PROJECTS[0], "opensource", "zero_shot", 1)
            claude_out = rx.raw_output_path(REAL_PROJECTS[0], "claude", "zero_shot", 1)

            # Must assert existence INSIDE the sandbox context: _SandboxedBatch's
            # __exit__ deletes the temp tree, so checking .exists() after the
            # `with` block exits would always read False regardless of what
            # main() actually wrote - a false negative waiting to happen.
            self.assertEqual(len(jobs), 2)  # claude + gpt: submitted, not run synchronously
            self.assertTrue(opensource_out.exists())  # opensource: ran synchronously in the same call
            self.assertFalse(claude_out.exists())  # claude was batched, not run synchronously

        self.assertEqual(len(claude_batches.create_calls), 1)
        self.assertEqual(len(gpt_batches.create_calls), 1)


if __name__ == "__main__":
    unittest.main()
