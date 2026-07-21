"""Unit tests for analysis/make_figures.py.

Two things worth locking down here.

First, the `_show()` path-display bug class, which has now appeared three times
in this repo (build_rater_packets.py, then make_figures.py twice - once for a
relative --out-dir, once for an out-of-repo one). It is always cosmetic and
always crashes AFTER the real work succeeded, which is exactly why it keeps
slipping through manual checks: the figures are sitting there correctly written
while the process exits non-zero.

Second, schema tolerance. `metrics.py` gained new top-level keys on 2026-07-21
(`*_corpus_wide_only`, `by_category_excluding_parse_failures`) after this script
was written. Those additions turned out to be purely additive, but the figures
code reads `metrics.json` by key, so a rename or removal upstream would break
the paper's figures silently at the next run. These tests fail loudly instead.

Rendering uses matplotlib's Agg backend (no display needed) but does require
matplotlib to be installed - the tests skip cleanly if it isn't, so the suite
still runs on a bare interpreter.

Run: python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))

try:
    import make_figures as mf
    HAVE_MPL = True
except ImportError:  # matplotlib not installed in this interpreter
    HAVE_MPL = False


def _metrics_fixture():
    """A minimal metrics.json in the CURRENT schema, including the keys added
    on 2026-07-21, with every value hand-set so the figures are predictable."""
    cell = {"n_runs": 2, "mean_recall": 0.5, "mean_precision": 0.4,
            "mean_category_accuracy": 0.8, "n_parse_failed": 0}
    return {
        "n_scored_runs_total": 36,
        "n_parse_failed_total": 2,
        "corpus_wide": {"n_runs": 18, "mean_recall": 0.55, "mean_precision": 0.42,
                        "mean_category_accuracy": 0.81},
        "by_model_and_prompt": {f"{m} / {p}": dict(cell)
                                for m in mf.MODELS for p in mf.PROMPTS},
        "by_model_and_prompt_corpus_wide_only": {f"{m} / {p}": dict(cell)
                                                 for m in mf.MODELS for p in mf.PROMPTS},
        "by_category": {
            "technical": {"missed_count": 5, "hallucinated_count": 3},
            "environmental": {"missed_count": 4, "hallucinated_count": 0},
            "other": {"missed_count": 2, "hallucinated_count": 0},
        },
        "by_category_corpus_wide_only": {"technical": {"missed_count": 3, "hallucinated_count": 2}},
        "by_category_excluding_parse_failures": {"technical": {"missed_count": 2, "hallucinated_count": 3}},
        "short_register_subgroup": {"n_runs": 18, "mean_recall": 0.6, "mean_precision": 0.15,
                                    "mean_category_accuracy": 0.7, "by_project": {}},
        "per_run": [],
    }


@unittest.skipUnless(HAVE_MPL, "matplotlib not installed in this interpreter")
class TestShowPathHelper(unittest.TestCase):
    def test_inside_repo_path_is_shown_relative(self):
        p = REPO / "analysis" / "figures" / "fig_rq1_recall_precision.png"
        shown = mf._show(p)
        self.assertFalse(Path(shown).is_absolute())
        self.assertIn("figures", shown)

    def test_outside_repo_path_falls_back_to_absolute_instead_of_raising(self):
        # The 2026-07-21 crash: rendering into a scratch dir outside the repo
        # wrote all three figures correctly and then died on the print.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "fig.png"
            shown = mf._show(p)          # must not raise
            self.assertTrue(Path(shown).is_absolute())

    def test_relative_path_is_resolved_not_raised(self):
        self.assertIsInstance(mf._show(Path("analysis/figures/x.png")), str)


@unittest.skipUnless(HAVE_MPL, "matplotlib not installed in this interpreter")
class TestFiguresRenderAgainstCurrentSchema(unittest.TestCase):
    def test_all_three_figures_render(self):
        m = _metrics_fixture()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            paths = [mf.fig_rq1(m, "SYNTHETIC", out),
                     mf.fig_rq2(m, "SYNTHETIC", out),
                     mf.fig_rq3(m, "SYNTHETIC", out)]
            for p in paths:
                self.assertTrue(p.exists(), f"{p.name} not written")
                self.assertGreater(p.stat().st_size, 1000, f"{p.name} suspiciously small")

    def test_figures_render_into_a_directory_outside_the_repo(self):
        # End-to-end version of the _show regression, through the real fig_* fns.
        m = _metrics_fixture()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "nested" / "figs"
            out.mkdir(parents=True)
            p = mf.fig_rq1(m, "", out)
            self.assertTrue(p.exists())
            mf._show(p)   # the step that used to raise

    def test_rq2_matrix_shape_and_values(self):
        m = _metrics_fixture()
        mat = mf._grid_matrix(m, "mean_recall")
        self.assertEqual(mat.shape, (len(mf.MODELS), len(mf.PROMPTS)))
        self.assertAlmostEqual(float(mat[0, 0]), 0.5)

    def test_rq2_missing_cell_does_not_crash(self):
        # A partial grid (e.g. a resumed run) must still plot.
        m = _metrics_fixture()
        del m["by_model_and_prompt"]["claude / zero_shot"]
        mat = mf._grid_matrix(m, "mean_recall")
        self.assertEqual(mat.shape, (len(mf.MODELS), len(mf.PROMPTS)))

    def test_bars_or_zero_handles_none(self):
        # metrics.py returns None for undefined means; matplotlib cannot plot None.
        self.assertEqual(mf._bars_or_zero(None), 0)
        self.assertEqual(mf._bars_or_zero(0.5), 0.5)


@unittest.skipUnless(HAVE_MPL, "matplotlib not installed in this interpreter")
class TestMetricsSchemaContract(unittest.TestCase):
    """The keys make_figures reads must be exactly the keys metrics.py emits.
    Computed from a real metrics.py run over synthetic fixtures rather than
    hardcoded, so upstream renames surface here rather than in the paper."""

    def test_figure_inputs_exist_in_a_real_metrics_report(self):
        sys.path.insert(0, str(REPO / "src"))
        import metrics as met

        # Two tiny match results are enough for compute_all to emit full schema.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            payload = {
                "project_id": "P-SRB-CompetitivenessJobs", "model": "claude",
                "prompt_strategy": "zero_shot", "run_index": 1, "parse_failed": False,
                "gen_risks": [{"risk_id": "R01", "category": "schedule"},
                              {"risk_id": "R02", "category": "technical"}],
                "gt_risks": [{"risk_id": "G01", "category": "schedule"}],
                "matches": [{"gen_risk_id": "R01", "gt_risk_id": "G01",
                             "gen_category": "schedule", "gt_category": "schedule",
                             "category_agree": True}],
            }
            (tmp / "a.match.json").write_text(json.dumps(payload), encoding="utf-8")
            report = met.compute_all(scored_dir=tmp)

        # These are the top-level keys the three figures actually index into.
        for key in ("corpus_wide", "by_model_and_prompt", "by_category",
                    "short_register_subgroup"):
            self.assertIn(key, report, f"make_figures reads {key!r}; metrics.py no longer emits it")

        for field in ("mean_recall", "mean_precision"):
            self.assertIn(field, report["corpus_wide"],
                          f"fig_rq1 reads corpus_wide[{field!r}]")
        cell = next(iter(report["by_model_and_prompt"].values()))
        for field in ("mean_recall", "mean_precision"):
            self.assertIn(field, cell, f"fig_rq2 reads by_model_and_prompt[*][{field!r}]")
        cat = next(iter(report["by_category"].values()))
        for field in ("missed_count", "hallucinated_count"):
            self.assertIn(field, cat, f"fig_rq3 reads by_category[*][{field!r}]")


if __name__ == "__main__":
    unittest.main()
