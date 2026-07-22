"""validate_threshold.py - empirically check match.py's embedding model and
similarity threshold against a hand-labeled risk-pair set.

Why this exists: match.py's own docstring flags EMBEDDING_MODEL
(all-MiniLM-L6-v2) and MATCH_THRESHOLD (0.5) as "first-pass defaults, not
empirically validated against this corpus," and asks that any recall/precision
numbers produced before the threshold is validated "against a labeled sample"
be treated as provisional. This script provides that labeled sample and the
validation.

What it does:
  1. Loads analysis/threshold_validation_pairs.json - hand-labeled
     should-match / should-not-match risk pairs across a WB register
     (P-STP-YouthEmployment) and a UK register (P-UK-HyNetCCUSCluster), plus
     cross-project pairs. See that file's _meta for the honest scope: the
     ground-truth side of each pair is real text drawn from committed
     registers, though - corrected 2026-07-21 after checking all 24 sides
     against the real files - not always the complete verbatim field (most
     are excerpts truncated at a clause boundary; none are fabricated or
     paraphrased). The generated side is hand-written to emulate model output
     (no real model output exists yet - no API keys).
  2. Embeds each side with the SAME model and SAME cosine function match.py
     uses at runtime (imported directly from match.py, not reimplemented), on
     both the description+mitigation concatenation match.py actually embeds
     and description-only (a sensitivity check).
  3. On the unambiguous pairs (tiers clear_positive / clear_negative), sweeps
     candidate thresholds and reports, per threshold: sensitivity (true
     matches recovered), specificity (true non-matches rejected), precision,
     F1, accuracy, and Youden's J. Recommends a threshold from the separation
     between the positive and negative similarity distributions.
  4. Reports the hard_case (granularity-mismatch) pairs separately - they are
     NOT used to pick the threshold because the human label itself is a
     judgment call, but they show where realistic borderline pairs land.
  5. As an end-to-end check, runs match.py's real match_project() on the one
     pilot generation that exists (scratch/pilot_STP_zeroshot.json) against
     P-STP-YouthEmployment ground truth at each candidate threshold.

Writes a markdown report to results/threshold_validation_report.md and prints
a summary. This script does NOT modify match.py; if the evidence supports
changing the default threshold, that edit is applied separately and this
report is the justification for it.

Usage:
  python src/validate_threshold.py
  python src/validate_threshold.py --thresholds 0.3,0.35,0.4,0.45,0.5,0.55,0.6
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import match  # reuse the ACTUAL runtime model + cosine + matching code

REPO_ROOT = Path(__file__).resolve().parent.parent
PAIRS_PATH = REPO_ROOT / "analysis" / "threshold_validation_pairs.json"
PILOT_PATH = REPO_ROOT / "scratch" / "pilot_STP_zeroshot.json"
STP_GT_PATH = REPO_ROOT / "data" / "ground_truth" / "P-STP-YouthEmployment.json"
REPORT_PATH = REPO_ROOT / "results" / "threshold_validation_report.md"

DEFAULT_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def _show(path: Path) -> str:
    """Repo-relative display where possible, else the absolute path. A
    --report path outside the repo is legal and must not crash after the real
    work is already done - same fix as build_rater_packets.py, make_figures.py,
    judge.py, and match.py; this project has hit this exact crash class five
    times now."""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(Path(path).resolve())


def concat(side: dict) -> str:
    """Same field concatenation match.risk_text() uses: description + mitigation."""
    return f"{side.get('description', '')} {side.get('mitigation') or ''}".strip()


def embed_pairs(pairs: list[dict], model_name: str) -> list[dict]:
    """Attach cosine similarity (desc+mit, and desc-only) to each pair, using
    match.py's own model loader and cosine function."""
    model = match._get_model(model_name)

    a_full = [concat(p["a"]) for p in pairs]
    b_full = [concat(p["b"]) for p in pairs]
    a_desc = [p["a"].get("description", "") for p in pairs]
    b_desc = [p["b"].get("description", "") for p in pairs]

    va_full = model.encode(a_full, convert_to_numpy=True, show_progress_bar=False)
    vb_full = model.encode(b_full, convert_to_numpy=True, show_progress_bar=False)
    va_desc = model.encode(a_desc, convert_to_numpy=True, show_progress_bar=False)
    vb_desc = model.encode(b_desc, convert_to_numpy=True, show_progress_bar=False)

    # Diagonal of the pairwise cosine matrix = each row's own pair similarity.
    sim_full = match._cosine_matrix(va_full, vb_full)
    sim_desc = match._cosine_matrix(va_desc, vb_desc)

    out = []
    for i, p in enumerate(pairs):
        q = dict(p)
        q["sim_desc_plus_mit"] = round(float(sim_full[i, i]), 4)
        q["sim_desc_only"] = round(float(sim_desc[i, i]), 4)
        out.append(q)
    return out


def sweep(clear_pairs: list[dict], thresholds: list[float], sim_key: str) -> list[dict]:
    positives = [p[sim_key] for p in clear_pairs if p["expected_match"]]
    negatives = [p[sim_key] for p in clear_pairs if not p["expected_match"]]
    rows = []
    for t in thresholds:
        tp = sum(1 for s in positives if s >= t)
        fn = len(positives) - tp
        fp = sum(1 for s in negatives if s >= t)
        tn = len(negatives) - fp
        sens = tp / (tp + fn) if (tp + fn) else None
        spec = tn / (tn + fp) if (tn + fp) else None
        prec = tp / (tp + fp) if (tp + fp) else None
        f1 = (2 * prec * sens / (prec + sens)) if (prec and sens and (prec + sens)) else 0.0
        acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else None
        youden = (sens + spec - 1) if (sens is not None and spec is not None) else None
        rows.append({
            "threshold": t, "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "sensitivity": sens, "specificity": spec, "precision": prec,
            "f1": round(f1, 3), "accuracy": round(acc, 3) if acc is not None else None,
            "youden_j": round(youden, 3) if youden is not None else None,
        })
    return rows


def distribution(vals: list[float]) -> dict:
    if not vals:
        return {}
    return {
        "n": len(vals),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "mean": round(statistics.mean(vals), 4),
        "median": round(statistics.median(vals), 4),
    }


def recommend(clear_pairs: list[dict], sim_key: str, sweep_rows: list[dict]) -> dict:
    positives = [p[sim_key] for p in clear_pairs if p["expected_match"]]
    negatives = [p[sim_key] for p in clear_pairs if not p["expected_match"]]
    min_pos, max_neg = min(positives), max(negatives)
    separable = min_pos > max_neg
    best_youden = max(sweep_rows, key=lambda r: (r["youden_j"] if r["youden_j"] is not None else -9, r["f1"]))
    best_f1 = max(sweep_rows, key=lambda r: (r["f1"], r["youden_j"] if r["youden_j"] is not None else -9))
    rec = {
        "sim_key": sim_key,
        "positives_dist": distribution(positives),
        "negatives_dist": distribution(negatives),
        "separable": separable,
        "gap_low_max_negative": round(max_neg, 4),
        "gap_high_min_positive": round(min_pos, 4),
        "gap_midpoint": round((max_neg + min_pos) / 2, 4) if separable else None,
        "best_youden_threshold": best_youden["threshold"],
        "best_youden_j": best_youden["youden_j"],
        "best_f1_threshold": best_f1["threshold"],
        "best_f1": best_f1["f1"],
    }
    return rec


def run_pilot_endtoend(thresholds: list[float]) -> dict | None:
    if not PILOT_PATH.exists() or not STP_GT_PATH.exists():
        return None
    generated = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    ground_truth = json.loads(STP_GT_PATH.read_text(encoding="utf-8"))
    rows = []
    for t in thresholds:
        res = match.match_project(generated, ground_truth, threshold=t)
        rows.append({
            "threshold": t,
            "n_matched": len(res["matches"]),
            "n_generated": len(res["gen_risks"]),
            "n_ground_truth": len(res["gt_risks"]),
            "matches": [
                {"gen": m["gen_risk_id"], "gt": m["gt_risk_id"], "sim": m["similarity"]}
                for m in res["matches"]
            ],
        })
    return {
        "generated_file": str(PILOT_PATH.relative_to(REPO_ROOT)),
        "n_generated": len(generated.get("risks", [])),
        "n_ground_truth": len(ground_truth.get("risks", [])),
        "by_threshold": rows,
    }


def fmt_pct(x) -> str:
    return f"{x:.2f}" if x is not None else "-"


def build_report(model_name, thresholds, embedded, sweep_full, sweep_desc,
                 rec_full, rec_desc, pilot) -> str:
    clear = [p for p in embedded if p["tier"] in ("clear_positive", "clear_negative")]
    hard = [p for p in embedded if p["tier"] == "hard_case"]
    L = []
    L.append("# Threshold & embedding-model validation report")
    L.append("")
    L.append(f"- Embedding model: `{model_name}` (match.py's `EMBEDDING_MODEL`)")
    L.append(f"- Current default `MATCH_THRESHOLD` in match.py: **{match.MATCH_THRESHOLD}** "
             f"(was 0.5 before this validation; see match.py comment)")
    L.append(f"- Labeled pairs: {len(clear)} unambiguous (drive the recommendation) + "
             f"{len(hard)} hard/borderline (reported only)")
    L.append(f"- Primary metric: cosine on **description+mitigation** (what match.py embeds). "
             f"Description-only shown as a sensitivity.")
    L.append("")
    L.append("> **Scope caveat (important):** the generated side of each pair is hand-written to "
             "emulate model output; no real model output exists yet (no API keys). This is a "
             "realistic labeled sample, not a harvested one. The recommendation below is therefore "
             "'validated against a hand-built labeled set,' which is stronger than an unvalidated "
             "default but should be revisited once a real experiment run exists. See "
             "`analysis/threshold_validation_pairs.json` `_meta`.")
    L.append("")

    L.append("## 1. Similarity distributions (unambiguous pairs, desc+mitigation)")
    L.append("")
    L.append(f"- **Should-match** pairs (n={rec_full['positives_dist'].get('n')}): "
             f"min={rec_full['positives_dist'].get('min')}, "
             f"mean={rec_full['positives_dist'].get('mean')}, "
             f"max={rec_full['positives_dist'].get('max')}")
    L.append(f"- **Should-NOT-match** pairs (n={rec_full['negatives_dist'].get('n')}): "
             f"min={rec_full['negatives_dist'].get('min')}, "
             f"mean={rec_full['negatives_dist'].get('mean')}, "
             f"max={rec_full['negatives_dist'].get('max')}")
    L.append("")
    if rec_full["separable"]:
        L.append(f"The two classes are **cleanly separable** on this set: the highest "
                 f"should-not-match similarity ({rec_full['gap_low_max_negative']}) is below the "
                 f"lowest should-match similarity ({rec_full['gap_high_min_positive']}). Any "
                 f"threshold in that gap separates them perfectly; the gap midpoint is "
                 f"**{rec_full['gap_midpoint']}**.")
    else:
        L.append(f"The two classes **overlap** on this set (highest negative "
                 f"{rec_full['gap_low_max_negative']} >= lowest positive "
                 f"{rec_full['gap_high_min_positive']}): no threshold separates them perfectly. "
                 f"Best trade-off thresholds are reported in the sweep below.")
    L.append("")

    L.append("## 2. Threshold sweep (unambiguous pairs, desc+mitigation)")
    L.append("")
    L.append("| threshold | TP | FN | FP | TN | sensitivity | specificity | precision | F1 | accuracy | Youden J |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sweep_full:
        L.append(f"| {r['threshold']:.2f} | {r['tp']} | {r['fn']} | {r['fp']} | {r['tn']} | "
                 f"{fmt_pct(r['sensitivity'])} | {fmt_pct(r['specificity'])} | "
                 f"{fmt_pct(r['precision'])} | {r['f1']:.2f} | "
                 f"{fmt_pct(r['accuracy'])} | {fmt_pct(r['youden_j'])} |")
    L.append("")
    L.append(f"- Best by Youden's J: threshold **{rec_full['best_youden_threshold']:.2f}** "
             f"(J={rec_full['best_youden_j']}). Best by F1: threshold "
             f"**{rec_full['best_f1_threshold']:.2f}** (F1={rec_full['best_f1']}).")
    L.append("")

    L.append("## 3. Sensitivity: description-only (mitigation dropped)")
    L.append("")
    L.append(f"- Should-match (n={rec_desc['positives_dist'].get('n')}): "
             f"mean={rec_desc['positives_dist'].get('mean')}, "
             f"min={rec_desc['positives_dist'].get('min')}, max={rec_desc['positives_dist'].get('max')}")
    L.append(f"- Should-NOT-match (n={rec_desc['negatives_dist'].get('n')}): "
             f"mean={rec_desc['negatives_dist'].get('mean')}, "
             f"min={rec_desc['negatives_dist'].get('min')}, max={rec_desc['negatives_dist'].get('max')}")
    sep = "separable" if rec_desc["separable"] else "overlapping"
    L.append(f"- Classes are **{sep}** on description-only; gap midpoint "
             f"{rec_desc['gap_midpoint']}. Best Youden threshold {rec_desc['best_youden_threshold']:.2f}.")
    L.append("")

    L.append("## 4. Hard / borderline cases (NOT used to pick the threshold)")
    L.append("")
    L.append("These are genuine granularity-mismatch judgment calls. They show where realistic "
             "borderline pairs land relative to the recommended threshold.")
    L.append("")
    L.append("| pair | register | human label | desc+mit sim | rationale |")
    L.append("|---|---|---|---|---|")
    for p in hard:
        lbl = "match" if p["expected_match"] else "no-match"
        conf = p.get("human_label_confidence", "?")
        L.append(f"| {p['pair_id']} | {p['register']} | {lbl} ({conf}) | "
                 f"{p['sim_desc_plus_mit']} | {p['rationale'][:120]} |")
    L.append("")

    L.append("## 5. Per-pair similarities (all pairs)")
    L.append("")
    L.append("| pair | tier | expected | desc+mit | desc-only |")
    L.append("|---|---|---|---|---|")
    for p in embedded:
        L.append(f"| {p['pair_id']} | {p['tier']} | "
                 f"{'match' if p['expected_match'] else 'no-match'} | "
                 f"{p['sim_desc_plus_mit']} | {p['sim_desc_only']} |")
    L.append("")

    if pilot is not None:
        L.append("## 6. End-to-end check: real match.py on the STP pilot generation")
        L.append("")
        L.append(f"`match_project()` run on `{pilot['generated_file']}` "
                 f"({pilot['n_generated']} generated risks) vs P-STP-YouthEmployment ground truth "
                 f"({pilot['n_ground_truth']} risks), at each threshold:")
        L.append("")
        L.append("| threshold | matches | of gen | of gt | matched pairs (gen->gt, sim) |")
        L.append("|---|---|---|---|---|")
        for r in pilot["by_threshold"]:
            mp = "; ".join(f"{m['gen']}->{m['gt']} ({m['sim']})" for m in r["matches"]) or "-"
            L.append(f"| {r['threshold']:.2f} | {r['n_matched']} | {r['n_generated']} | "
                     f"{r['n_ground_truth']} | {mp} |")
        L.append("")
        L.append("This is the real granularity-mismatch signal in action: the pilot generated "
                 "specific *implementation* risks while the ground truth lists broad *SORT* "
                 "categories, so even a well-tuned threshold recovers only the pairs that genuinely "
                 "correspond. Low match counts here are partly a real property of the task, not "
                 "purely a threshold artifact - which is exactly why the recommendation is anchored "
                 "on the hand-labeled clear pairs, not on this count.")
        L.append("")

    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thresholds", type=str, default=None,
                        help="Comma-separated thresholds to sweep (default 0.30..0.70 by 0.05)")
    parser.add_argument("--model", type=str, default=match.EMBEDDING_MODEL,
                        help=f"Embedding model (default match.py's {match.EMBEDDING_MODEL})")
    parser.add_argument("--report", type=str, default=str(REPORT_PATH))
    args = parser.parse_args()

    thresholds = ([float(x) for x in args.thresholds.split(",")]
                  if args.thresholds else DEFAULT_THRESHOLDS)

    fixture = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    pairs = fixture["pairs"]
    print(f"[validate] loaded {len(pairs)} labeled pairs; embedding with {args.model} ...")
    embedded = embed_pairs(pairs, args.model)

    clear = [p for p in embedded if p["tier"] in ("clear_positive", "clear_negative")]
    sweep_full = sweep(clear, thresholds, "sim_desc_plus_mit")
    sweep_desc = sweep(clear, thresholds, "sim_desc_only")
    rec_full = recommend(clear, "sim_desc_plus_mit", sweep_full)
    rec_desc = recommend(clear, "sim_desc_only", sweep_desc)
    pilot = run_pilot_endtoend(thresholds)

    report = build_report(args.model, thresholds, embedded, sweep_full, sweep_desc,
                          rec_full, rec_desc, pilot)
    out_path = Path(args.report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print(f"\n[validate] desc+mit: positives mean={rec_full['positives_dist'].get('mean')}, "
          f"negatives mean={rec_full['negatives_dist'].get('mean')}, "
          f"separable={rec_full['separable']}, gap_midpoint={rec_full['gap_midpoint']}")
    print(f"[validate] best Youden threshold={rec_full['best_youden_threshold']:.2f} "
          f"(J={rec_full['best_youden_j']}); best F1 threshold={rec_full['best_f1_threshold']:.2f} "
          f"(F1={rec_full['best_f1']})")
    print(f"[validate] current default MATCH_THRESHOLD={match.MATCH_THRESHOLD}")
    print(f"[validate] report written to {_show(out_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
