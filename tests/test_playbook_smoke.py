"""Task F10 - runs the real CLI entry points from docs/run_playbook.md's
quick-start sequence back to back, in the order the playbook documents them,
each one reading the file the previous one actually wrote - not each
command's own isolated fixture.

This is deliberately different from the per-file driver tests
(test_run_experiments_driver.py, test_match_driver.py, test_metrics_driver.py,
test_figures.py): those each prove one command works in isolation against a
fixture built for that test. This proves the CHAIN holds - that step 7's
output is genuinely step 8's input in the shape step 8 expects, using ONE
shared sandboxed tree throughout, the same way a human following the
playbook would produce one tree of results. "Doc says X, code does Y" has hit
this project at least 3 times already (the --confirm-cost doc claim, two
separate relative_to(REPO_ROOT) crash-on-relative-path bugs) - this test
exists to catch the next one before a human does, particularly a rename or
flag change in one step that silently breaks the next.

Chained: run_experiments.py --project (full 3x3 grid for one real project,
stubbed providers) -> match.py --all (stubbed embedding model) -> metrics.py
--out -> analysis/make_figures.py --metrics. Uses one REAL, already-included
corpus project (P-UK-HyNetCCUSCluster - same choice as test_run_pipeline.py)
so PROCESSED_DIR/MANIFEST_PATH/PROMPTS_DIR/GROUND_TRUTH_DIR can stay pointed
at the real repo; only the WRITE-side directories are sandboxed, matching the
established convention in tests/test_run_pipeline.py's _SandboxedRun.

Not chained here: extract.py, audit_corpus.py, validate_threshold.py, and
build_rater_packets.py don't sit on this read-then-write chain (they don't
consume run_experiments' output the way match/metrics/figures do, or in
build_rater_packets' case are already covered end-to-end by
test_rater_packets.py) - each already has its own driver test for the
step-specific "doc says X" risk.

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
ANALYSIS = REPO / "analysis"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ANALYSIS))
import run_experiments as rx  # noqa: E402
import match  # noqa: E402
import metrics  # noqa: E402

try:
    import make_figures  # noqa: E402
    HAVE_MATPLOTLIB = True
except ImportError:  # matplotlib not installed in this interpreter - same
    HAVE_MATPLOTLIB = False   # graceful-skip convention test_figures.py already uses.
    make_figures = None

REAL_PROJECT = "P-UK-HyNetCCUSCluster"  # same real, already-included project
                                         # test_run_pipeline.py uses.


def _valid_register(project_id: str, tag: str) -> str:
    return json.dumps({
        "project_id": project_id,
        "risks": [{
            "risk_id": "R01",
            "description": f"{tag}: cross-party consent delays hold up the pipeline corridor.",
            "category": "political_regulatory",
            "likelihood": 3,
            "impact": 4,
            "mitigation": "Sequence consent applications ahead of construction.",
            "evidence": "Planning doc, delivery-schedule section.",
        }],
    })


class _StubProvider:
    """Same shape as test_run_pipeline.py's _StubProvider - records calls,
    returns a fixed valid register. One real wrinkle this smoke test caught
    on its first run: the `structured` prompt condition's own template
    (prompts/structured.txt) instructs the model to answer with
    'REASONING: ... FINAL JSON: {...}', and run_experiments.py's parser
    ONLY looks for JSON after that marker for that condition (see
    _FINAL_JSON_RE) - a bare JSON reply, fine for zero_shot/few_shot, comes
    back parse_failed for structured. A stub that ignores this would make
    all 3 structured cells look broken and mask a real parse failure behind
    a fake one. Detected here the same way the real prompt signals it: by
    checking for the marker text in the rendered prompt itself, since the
    provider callable isn't handed the prompt_strategy directly."""

    def __init__(self, tag: str):
        self.tag = tag
        self.calls = []

    def __call__(self, prompt, model_version, temperature, max_tokens):
        self.calls.append(prompt)
        body = _valid_register(REAL_PROJECT, self.tag)
        if "FINAL JSON:" in prompt:
            return f"REASONING: stubbed reasoning for a smoke test.\nFINAL JSON: {body}", True
        return body, True


class _StubEmbeddingModel:
    """Same shape as test_match_driver.py's _StubModel - fixed, deterministic
    vectors so match.py's cosine similarity is well-defined without a real
    sentence-transformer. Every text maps to the same vector here: the point
    of this smoke test is that the CHAIN doesn't break, not match quality
    (that's test_match.py's job)."""

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False):
        import numpy as np
        return np.array([[1.0, 0.0] for _ in texts], dtype=float)


class _SandboxedPlaybook:
    """One shared temp tree, playing the role of the repo's results/ and
    analysis/figures/ across all four modules at once. PROCESSED_DIR,
    MANIFEST_PATH, PROMPTS_DIR, and GROUND_TRUTH_DIR are deliberately left
    pointed at the real repo (same convention as test_run_pipeline.py) -
    only the write side is sandboxed."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        raw_outputs = root / "results" / "raw_outputs"
        scored = root / "results" / "scored"
        figures = root / "figures"
        raw_outputs.mkdir(parents=True, exist_ok=True)
        scored.mkdir(parents=True, exist_ok=True)
        figures.mkdir(parents=True, exist_ok=True)

        self.root = root
        self.raw_outputs = raw_outputs
        self.scored = scored
        self.figures = figures
        self.metrics_path = root / "results" / "metrics.json"

        self._patches = [
            mock.patch.object(rx, "REPO_ROOT", root),
            mock.patch.object(rx, "RAW_OUTPUTS_DIR", raw_outputs),
            mock.patch.object(rx, "RUN_CONFIG_LOG", root / "results" / "run_config.jsonl"),
            mock.patch.dict(rx.MODEL_DISPATCH, {
                "claude": _StubProvider("claude"),
                "gpt": _StubProvider("gpt"),
                "opensource": _StubProvider("opensource"),
            }),
            mock.patch.dict("os.environ", {
                "CLAUDE_MODEL_NAME": "claude-sonnet-5",
                "GPT_MODEL_NAME": "gpt-5.6-terra",
                "OPENSOURCE_MODEL_NAME": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            }),
            mock.patch.object(match, "REPO_ROOT", root),
            mock.patch.object(match, "RAW_OUTPUTS_DIR", raw_outputs),
            mock.patch.object(match, "SCORED_DIR", scored),
            mock.patch.object(match, "_get_model", return_value=_StubEmbeddingModel()),
            mock.patch.object(metrics, "SCORED_DIR", scored),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        self._td.cleanup()
        return False


class TestPlaybookChainRunsEndToEnd(unittest.TestCase):
    """Steps 6 (run_experiments) -> 7 (match, metrics) -> 9 (figures) of
    docs/run_playbook.md, chained through one shared sandbox."""

    def test_full_chain_from_run_experiments_to_figures(self):
        with _SandboxedPlaybook() as box:
            # --- Step 6 (synchronous): python run_experiments.py --project X ---
            # No --model/--prompt filter -> the documented default: every
            # model x every prompt for this one project (9 cells, --runs 1).
            argv = ["run_experiments.py", "--project", REAL_PROJECT, "--runs", "1"]
            with mock.patch.object(sys, "argv", argv):
                rx.main()  # must not raise SystemExit on the happy path

            written = sorted(box.raw_outputs.glob("*.json"))
            self.assertEqual(
                len(written), 9,
                f"Expected 9 raw output files (3 models x 3 prompts x 1 run), "
                f"got {len(written)}: {[p.name for p in written]}"
            )

            # --- Step 7a: python match.py --all ---
            argv = ["match.py", "--all"]
            with mock.patch.object(sys, "argv", argv):
                match.main()

            scored_files = sorted(box.scored.glob("*.match.json"))
            self.assertEqual(
                len(scored_files), 9,
                f"Expected 9 *.match.json files (one per raw output), got "
                f"{len(scored_files)}: {[p.name for p in scored_files]}"
            )
            # Every scored file should trace back to a run match.py could
            # actually parse - if the stubbed register above stopped being
            # schema-valid, this is where it would show up as parse_failed.
            for fp in scored_files:
                result = json.loads(fp.read_text(encoding="utf-8"))
                self.assertFalse(
                    result.get("parse_failed"),
                    f"{fp.name} was marked parse_failed - the stubbed "
                    f"register no longer matches what match.py expects"
                )

            # --- Step 7b: python metrics.py --scored-dir ... --out ... ---
            argv = ["metrics.py", "--out", str(box.metrics_path)]
            with mock.patch.object(sys, "argv", argv):
                metrics.main()

            self.assertTrue(box.metrics_path.exists(), "metrics.py --out did not write a file")
            report = json.loads(box.metrics_path.read_text(encoding="utf-8"))
            for key in (
                "n_scored_runs_total", "corpus_wide", "by_model_and_prompt",
                "by_category", "per_run",
            ):
                self.assertIn(key, report, f"metrics.py's report is missing expected key {key!r}")
            self.assertEqual(report["n_scored_runs_total"], 9)
            self.assertEqual(len(report["per_run"]), 9)

            # --- Step 9: python analysis/make_figures.py --metrics ... ---
            # Guarded rather than a class-level skipUnless (matching
            # test_figures.py's HAVE_MPL convention): the run_experiments ->
            # match -> metrics portion above is real coverage on any
            # interpreter, matplotlib or not, and shouldn't be skipped
            # wholesale just because this last step can't run here. Found
            # 2026-07-22: a bare top-level `import make_figures` crashed this
            # entire test MODULE (not just this one test) on an interpreter
            # without matplotlib - exactly the failure run_playbook.md's own
            # Sec.0 warns about - since unlike test_figures.py this file
            # didn't originally guard the import.
            if not HAVE_MATPLOTLIB:
                self.skipTest("matplotlib not installed in this interpreter - "
                               "same skip test_figures.py uses; steps 6-7 above still ran")

            argv = [
                "make_figures.py",
                "--metrics", str(box.metrics_path),
                "--out-dir", str(box.figures),
                "--note", "SMOKE TEST - not real results",
            ]
            with mock.patch.object(sys, "argv", argv):
                exit_code = make_figures.main()

            self.assertEqual(exit_code, 0)
            expected_figures = [
                "fig_rq1_recall_precision.png",
                "fig_rq2_model_prompt.png",
                "fig_rq3_missed_hallucinated.png",
            ]
            for name in expected_figures:
                self.assertTrue(
                    (box.figures / name).exists(),
                    f"make_figures.py did not write {name} into --out-dir"
                )
                self.assertGreater(
                    (box.figures / name).stat().st_size, 0,
                    f"{name} exists but is empty"
                )

    def test_chain_is_append_only_across_steps(self):
        # Running steps 6 then 6 again with a HIGHER --runs target (as the
        # playbook explicitly documents as safe - "a partial grid is safe to
        # resume by just running the command again") should top up to the
        # new target, not clobber run1, and match.py --all should then see
        # both.
        with _SandboxedPlaybook() as box:
            argv1 = ["run_experiments.py", "--project", REAL_PROJECT,
                     "--model", "claude", "--prompt", "zero_shot", "--runs", "1"]
            with mock.patch.object(sys, "argv", argv1):
                rx.main()

            argv2 = ["run_experiments.py", "--project", REAL_PROJECT,
                     "--model", "claude", "--prompt", "zero_shot", "--runs", "2"]
            with mock.patch.object(sys, "argv", argv2):
                rx.main()  # re-invoke, same cell, higher target -> tops up

            written = sorted(box.raw_outputs.glob("*.json"))
            self.assertEqual(
                len(written), 2,
                f"Re-running with a higher --runs target should top up to "
                f"run2, not clobber run1: found {[p.name for p in written]}"
            )

            argv = ["match.py", "--all"]
            with mock.patch.object(sys, "argv", argv):
                match.main()
            self.assertEqual(len(list(box.scored.glob("*.match.json"))), 2)

    def test_reinvoking_the_same_runs_target_is_idempotent(self):
        # FIX 2026-07-25: this is the actual daily-resumption
        # scenario (re-running `--runs 2` once a day until the grid clears) -
        # a cell already satisfied at the requested --runs target must NOT
        # get more runs piled on top just because the same command ran again.
        # Before this fix, `main()` unconditionally looped `range(args.runs)`
        # every invocation, so re-running `--runs 2` daily kept adding 2 MORE
        # runs to every cell forever, wasting scarce daily quota on
        # already-satisfied cells instead of reaching untouched ones.
        with _SandboxedPlaybook() as box:
            argv = ["run_experiments.py", "--project", REAL_PROJECT,
                    "--model", "claude", "--prompt", "zero_shot", "--runs", "2"]
            with mock.patch.object(sys, "argv", argv):
                rx.main()
            with mock.patch.object(sys, "argv", argv):
                rx.main()  # re-invoke, same target - must be a no-op

            written = sorted(box.raw_outputs.glob("*.json"))
            self.assertEqual(
                len(written), 2,
                f"Re-invoking the same --runs target should be idempotent, "
                f"not add more runs: found {[p.name for p in written]}"
            )


if __name__ == "__main__":
    unittest.main()
