"""Unit tests for src/run_experiments.py's plain SYNCHRONOUS main() CLI path.

test_batch.py already covers --batch/--batch-check flag combinations
thoroughly - every rx.main() call in that file exercises one of those. This
file covers the plain grid loop instead: --project/--model/--prompt
filtering, --estimate-only's short-circuit before any run_one() call and
before the cost guard, the cost guard itself tripping/being bypassed via
--confirm-cost, and the two exit codes at the bottom of main() -
sys.exit(2) when every cell fails, sys.exit(3) when some (not all) fail.
None of this had any coverage anywhere in the suite before this file
(confirmed by grep: the only rx.main() calls anywhere were the 4 in
test_batch.py, all exercising --batch/--batch-check).

run_one() is stubbed throughout via mock.patch.object(rx, "run_one", ...) so
nothing here needs a real API key, network, or provider SDK - the point is
main()'s own dispatch/filtering/accounting logic, not run_one()'s internals
(already covered elsewhere).

Run: python -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import run_experiments as rx  # noqa: E402

REAL_PROJECTS = rx.all_project_ids()[:2]


class _SandboxedRun:
    """Isolates REPO_ROOT/RAW_OUTPUTS_DIR/RUN_CONFIG_LOG/BATCH_JOBS_LOG in a
    temp tree so next_free_run_index()'s filesystem/batch-log checks never
    touch the real results/ directory. PROCESSED_DIR/MANIFEST_PATH/
    PROMPTS_DIR/GROUND_TRUTH_DIR are deliberately left pointed at the real
    repo, the same choice test_batch.py's _SandboxedBatch makes - main()
    needs a real manifest and real processed text to build a real grid, and
    every test in this file stubs run_one() directly, so no provider is ever
    actually called regardless.

    The 3 *_MODEL_NAME env vars are set the same way _SandboxedBatch sets
    them, and matter even though run_one() is stubbed: estimate_cost() calls
    resolve_model_version() to look up pricing BEFORE run_one() is ever
    reached, and with no model name configured that lookup falls back to a
    placeholder string with no PRICING_PER_MTOK entry - silently zeroing the
    estimate and making the cost guard untestable. Found by running this
    file's own cost-guard test and getting exit code 2 (every cell "failed",
    because run_one was in fact reached) instead of the expected 1."""

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


def _argv(*extra):
    return ["run_experiments.py", "--project", REAL_PROJECTS[0], "--model", "claude",
            "--prompt", "zero_shot"] + list(extra)


def _never_called(*a, **k):
    raise AssertionError("run_one must not be called on this path")


class TestProjectModelPromptFiltering(unittest.TestCase):
    """--project/--model/--prompt are all argparse action='append' - repeated
    flags should accumulate, and the three lists cross-product into cells,
    same as the grid comprehension in main() itself builds them."""

    def _captured_cells(self, argv):
        captured = {}
        real_estimate_cost = rx.estimate_cost

        def spy(cells, *a, **k):
            captured["cells"] = cells
            return real_estimate_cost(cells, *a, **k)

        with _SandboxedRun():
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(rx, "estimate_cost", side_effect=spy):
                rx.main()
        return captured["cells"]

    def test_single_project_model_prompt_is_exactly_one_cell(self):
        cells = self._captured_cells(_argv("--estimate-only"))
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0].project_id, REAL_PROJECTS[0])
        self.assertEqual(cells[0].model_label, "claude")
        self.assertEqual(cells[0].prompt_strategy, "zero_shot")

    def test_repeatable_model_flag_expands_the_grid(self):
        argv = ["run_experiments.py", "--project", REAL_PROJECTS[0], "--model", "claude",
                "--model", "gpt", "--prompt", "zero_shot", "--estimate-only"]
        cells = self._captured_cells(argv)
        self.assertEqual(len(cells), 2)
        self.assertEqual({c.model_label for c in cells}, {"claude", "gpt"})

    def test_project_and_prompt_repeats_cross_product_to_four_cells(self):
        argv = ["run_experiments.py",
                "--project", REAL_PROJECTS[0], "--project", REAL_PROJECTS[1],
                "--model", "claude",
                "--prompt", "zero_shot", "--prompt", "few_shot",
                "--estimate-only"]
        cells = self._captured_cells(argv)
        self.assertEqual(len(cells), 4)
        self.assertEqual({c.project_id for c in cells}, set(REAL_PROJECTS))
        self.assertEqual({c.prompt_strategy for c in cells}, {"zero_shot", "few_shot"})

    def test_no_filters_defaults_to_the_full_real_grid(self):
        # Exercises the documented default ("all in data/processed/" / "all
        # three") against the REAL manifest and REAL MODEL_DISPATCH/PROMPT_FILES
        # - not a fixture - so a future corpus or grid-size change is exactly
        # what would (correctly) break this test.
        argv = ["run_experiments.py", "--estimate-only"]
        cells = self._captured_cells(argv)
        expected = len(rx.all_project_ids()) * len(rx.MODEL_DISPATCH) * len(rx.PROMPT_FILES)
        self.assertEqual(len(cells), expected)


class TestEstimateOnlyShortCircuits(unittest.TestCase):
    def test_estimate_only_never_calls_run_one(self):
        with _SandboxedRun():
            with mock.patch.object(sys, "argv", _argv("--estimate-only")), \
                 mock.patch.object(rx, "run_one", side_effect=_never_called):
                rx.main()  # must not raise (would raise AssertionError if run_one were called)

    def test_estimate_only_does_not_trip_the_cost_guard_even_over_threshold(self):
        # --estimate-only returns before the guard check regardless of cost -
        # the full unfiltered grid ($42+ at --runs 2, confirmed elsewhere this
        # session) must still exit cleanly with no --confirm-cost passed.
        with _SandboxedRun():
            argv = ["run_experiments.py", "--runs", "2", "--estimate-only"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(rx, "run_one", side_effect=_never_called):
                rx.main()  # must not raise SystemExit at all


class TestCostGuardViaMainCLI(unittest.TestCase):
    """test_run_pipeline.py checks COST_GUARD_THRESHOLD_USD's value directly;
    nothing before this file exercised the guard through main()'s own CLI
    dispatch."""

    def test_over_threshold_without_confirm_cost_exits_1_and_never_calls_run_one(self):
        with _SandboxedRun():
            argv = ["run_experiments.py", "--runs", "2"]   # full grid, no --confirm-cost: $42+ > $30
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(rx, "run_one", side_effect=_never_called):
                with self.assertRaises(SystemExit) as cm:
                    rx.main()
        self.assertEqual(cm.exception.code, 1)

    def test_confirm_cost_bypasses_the_guard_and_runs_every_cell(self):
        calls = []

        def fake_run_one(project_id, model_label, prompt_strategy, run_index, temperature, max_tokens):
            calls.append((project_id, model_label, prompt_strategy, run_index))
            return rx.raw_output_path(project_id, model_label, prompt_strategy, run_index)

        with _SandboxedRun():
            argv = ["run_experiments.py", "--runs", "2", "--confirm-cost"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(rx, "run_one", side_effect=fake_run_one):
                rx.main()  # must not raise

        expected_calls = len(rx.all_project_ids()) * len(rx.MODEL_DISPATCH) * len(rx.PROMPT_FILES) * 2
        self.assertEqual(len(calls), expected_calls)


class TestExitCodes(unittest.TestCase):
    def test_all_cells_succeed_returns_normally(self):
        def fake_run_one(project_id, model_label, prompt_strategy, run_index, temperature, max_tokens):
            return rx.raw_output_path(project_id, model_label, prompt_strategy, run_index)

        with _SandboxedRun():
            with mock.patch.object(sys, "argv", _argv()), \
                 mock.patch.object(rx, "run_one", side_effect=fake_run_one):
                rx.main()  # must not raise SystemExit

    def test_every_cell_failing_exits_2(self):
        with _SandboxedRun():
            with mock.patch.object(sys, "argv", _argv()), \
                 mock.patch.object(rx, "run_one", side_effect=RuntimeError("simulated provider failure")):
                with self.assertRaises(SystemExit) as cm:
                    rx.main()
        self.assertEqual(cm.exception.code, 2)

    def test_partial_failure_exits_3(self):
        # Keyed on CALL ORDER, not the run_index argument: fake_run_one never
        # writes a real file, so next_free_run_index() (which decides
        # run_index by checking what's already on disk) hands out the SAME
        # index for both of --runs 2's iterations here - a real run_one()
        # wouldn't have this problem since it actually writes the file after
        # its first call. Confirmed by first writing this keyed on
        # run_index == 1/2 and seeing "SystemExit not raised" (both calls
        # happened to receive run_index=1, so both "succeeded").
        calls = {"n": 0}

        def fake_run_one(project_id, model_label, prompt_strategy, run_index, temperature, max_tokens):
            calls["n"] += 1
            if calls["n"] == 1:
                return rx.raw_output_path(project_id, model_label, prompt_strategy, run_index)
            raise RuntimeError("simulated provider failure on the second call")

        with _SandboxedRun():
            with mock.patch.object(sys, "argv", _argv("--runs", "2")), \
                 mock.patch.object(rx, "run_one", side_effect=fake_run_one):
                with self.assertRaises(SystemExit) as cm:
                    rx.main()
        self.assertEqual(cm.exception.code, 3)
        self.assertEqual(calls["n"], 2)

    def test_temperature_out_of_range_also_exits_2_characterization(self):
        # CHARACTERIZATION, not a bug: argparse's own parser.error() always
        # exits with code 2 too (its own unrelated convention) - an
        # out-of-range --temperature and "every cell failed" are NOT
        # distinguishable by exit code alone from outside the process. Pinned
        # so this overlap is a known fact, not a surprise discovered later by
        # a shell script that greps for "exit code 2" and assumes it always
        # means "every cell failed."
        with _SandboxedRun():
            with mock.patch.object(sys, "argv", _argv("--temperature", "0.9")):
                with self.assertRaises(SystemExit) as cm:
                    rx.main()
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
