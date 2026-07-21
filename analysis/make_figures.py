"""make_figures.py - render the paper's RQ1/RQ2/RQ3 figures from metrics.py output.

Consumes the JSON that `src/metrics.py --out <path>` writes (its compute_all()
report) and produces three PNGs in analysis/figures/:

  fig_rq1_recall_precision.png  - RQ1: corpus-wide mean recall & precision shown
      ALONGSIDE (never pooled with) the short-register subgroup's precision/recall.
  fig_rq2_model_prompt.png      - RQ2: how recall & precision vary across the
      3 models x 3 prompts (two annotated heatmaps).
  fig_rq3_missed_hallucinated.png - RQ3: per-category missed vs. hallucinated
      counts as diverging bars.

Design choices:
  - RQ2 uses two annotated heatmaps (recall, precision) rather than an 18-bar
    grouped chart: the RQ2 question is explicitly "how do results vary across
    models AND prompts", a 2-D interaction that a heatmap shows at a glance
    while the per-cell annotations still give exact values.
  - RQ3 handles category="other" correctly and LEGIBLY: generated risks can
    never be "other" (forbidden by prompts/output_schema.json's enum; see
    match.py's docstring), so "other" structurally always has
    hallucinated_count=0. That is expected, not missing data - the figure marks
    "other" with an asterisk and a caption note so it does not read as a gap.

The --note argument stamps a caption on every figure (used to mark synthetic /
pipeline-validation output so an illustrative figure is never mistaken for a
real result). This script does not know or care whether the metrics came from a
real run or synthetic fixtures - that distinction is the caller's to label.

Usage:
  python analysis/make_figures.py --metrics scratch/synthetic_metrics.json \\
      --note "SYNTHETIC - pipeline validation, not real results"
  python analysis/make_figures.py --metrics results/scored_metrics.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless render to PNG
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = REPO_ROOT / "analysis" / "figures"

MODELS = ["claude", "gpt", "opensource"]
PROMPTS = ["zero_shot", "few_shot", "structured"]


def _show(path: Path) -> str:
    """Repo-relative display where possible, else the absolute path. An
    --out-dir OUTSIDE the repo is legal (e.g. rendering synthetic figures into
    a scratch dir) and must not crash the final print after the figures have
    already been written. Same helper, same reason, as build_rater_packets.py's."""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _caption(fig, note: str) -> None:
    if note:
        fig.text(0.5, 0.005, note, ha="center", va="bottom", fontsize=8,
                 style="italic", color="#b00020")


def _bars_or_zero(v):
    return 0.0 if v is None else v


def fig_rq1(metrics: dict, note: str, out_dir: Path) -> Path:
    cw = metrics["corpus_wide"]
    sg = metrics["short_register_subgroup"]
    groups = ["Corpus-wide\n(ordinary docs)", "Short-register subgroup\n(thin docs, reported separately)"]
    recall = [_bars_or_zero(cw.get("mean_recall")), _bars_or_zero(sg.get("mean_recall"))]
    precision = [_bars_or_zero(cw.get("mean_precision")), _bars_or_zero(sg.get("mean_precision"))]

    x = np.arange(len(groups))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    b1 = ax.bar(x - w / 2, recall, w, label="Mean recall", color="#3b7dd8")
    b2 = ax.bar(x + w / 2, precision, w, label="Mean precision", color="#e0873b")
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                        ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("RQ1: Completeness (recall) & accuracy (precision) vs. ground truth\n"
                 "Two groups shown separately - never pooled into one number")
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    _caption(fig, note)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = out_dir / "fig_rq1_recall_precision.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _grid_matrix(metrics: dict, key: str) -> np.ndarray:
    bmp = metrics["by_model_and_prompt"]
    m = np.full((len(MODELS), len(PROMPTS)), np.nan)
    for i, model in enumerate(MODELS):
        for j, prompt in enumerate(PROMPTS):
            cell = bmp.get(f"{model} / {prompt}")
            if cell and cell.get(key) is not None:
                m[i, j] = cell[key]
    return m


def fig_rq2(metrics: dict, note: str, out_dir: Path) -> Path:
    recall = _grid_matrix(metrics, "mean_recall")
    precision = _grid_matrix(metrics, "mean_precision")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, mat, title, cmap in (
        (axes[0], recall, "Mean recall", "Blues"),
        (axes[1], precision, "Mean precision", "Oranges"),
    ):
        im = ax.imshow(mat, cmap=cmap, vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(PROMPTS)), labels=PROMPTS)
        ax.set_yticks(range(len(MODELS)), labels=MODELS)
        ax.set_xlabel("Prompt strategy")
        ax.set_ylabel("Model")
        ax.set_title(title)
        for i in range(len(MODELS)):
            for j in range(len(PROMPTS)):
                val = mat[i, j]
                txt = "n/a" if np.isnan(val) else f"{val:.2f}"
                # contrast: dark text on light cells, white on dark
                lum = 0 if np.isnan(val) else val
                ax.text(j, i, txt, ha="center", va="center",
                        color="white" if lum > 0.6 else "black", fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("RQ2: how completeness & accuracy vary across models x prompts", y=1.02)
    _caption(fig, note)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = out_dir / "fig_rq2_model_prompt.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def fig_rq3(metrics: dict, note: str, out_dir: Path) -> Path:
    by_cat = metrics["by_category"]
    cats = sorted(by_cat.keys())
    missed = [by_cat[c]["missed_count"] for c in cats]
    hallucinated = [by_cat[c]["hallucinated_count"] for c in cats]

    labels = [c + (" *" if c == "other" else "") for c in cats]
    y = np.arange(len(cats))
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(y, [-m for m in missed], color="#c0504d", label="Missed (in ground truth, not generated)")
    ax.barh(y, hallucinated, color="#4f81bd", label="Hallucinated (generated, not in ground truth)")
    for i, (m, h) in enumerate(zip(missed, hallucinated)):
        if m:
            ax.annotate(str(m), (-m, i), ha="right", va="center", fontsize=8, xytext=(-3, 0),
                        textcoords="offset points")
        if h:
            ax.annotate(str(h), (h, i), ha="left", va="center", fontsize=8, xytext=(3, 0),
                        textcoords="offset points")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(y, labels=labels)
    # Headroom on both sides so the count annotations aren't clipped at the axes edge.
    lo = -(max(missed) if missed else 0)
    hi = max(hallucinated) if hallucinated else 0
    span = max(hi - lo, 1)
    ax.set_xlim(lo - 0.08 * span, hi + 0.08 * span)
    ax.set_xlabel("<- missed count      |      hallucinated count ->")
    ax.set_title("RQ3: which risk categories are systematically missed vs. hallucinated")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    note2 = ("* 'other': generated risks can never be category 'other' (output-schema enum), "
             "so its hallucinated count is structurally 0 - expected, not missing data.")
    full_note = (note + "\n" + note2) if note else note2
    fig.text(0.5, 0.005, full_note, ha="center", va="bottom", fontsize=7.5,
             style="italic", color="#333333")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    out = out_dir / "fig_rq3_missed_hallucinated.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics", required=True, help="Path to metrics.py --out JSON")
    ap.add_argument("--out-dir", default=str(FIG_DIR))
    ap.add_argument("--note", default="", help="Caption stamped on every figure (e.g. a SYNTHETIC warning)")
    args = ap.parse_args()

    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    # .resolve() so the final _show(p) below works regardless of whether
    # --out-dir was passed as relative or absolute - found 2026-07-21 by
    # re-running this script with a relative --out-dir, which crashed on that
    # print AFTER the figures were already correctly written (cosmetic but
    # real: a relative override is a very normal thing to pass).
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = [
        fig_rq1(metrics, args.note, out_dir),
        fig_rq2(metrics, args.note, out_dir),
        fig_rq3(metrics, args.note, out_dir),
    ]
    for p in paths:
        print(f"[figures] wrote {_show(p)}")
    if args.note:
        print(f"[figures] NOTE stamped on all figures: {args.note!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
