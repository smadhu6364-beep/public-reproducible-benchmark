"""metrics.py - recall, precision, and per-category coverage from matches (Method A).

IMPLEMENTED 2026-07-19 with explicit user approval, after the project's own
10-document ground-truth validation gate was crossed (18/18 non-set-aside
documents). Consumes results/scored/*.match.json (written by match.py).

Responsibilities:
  - Per-run recall, precision, and per-category coverage vs. ground truth (RQ1).
  - Aggregate by model and prompt strategy (RQ2).
  - Aggregate by category across the corpus - which categories are most often
    missed (low recall) or most often hallucinated (unmatched generated risks'
    categories) (RQ3).
  - Break out the 5-document short-register/hallucination-test subgroup
    (P-KHM, P-PAK, P-JOR, P-MAR, P-UK-FreeBreakfastClubs - see
    corpus_manifest.csv 2026-07-19 decision notes and paper draft Section
    III.A/F) as its own reported block, never silently pooled into headline
    recall/precision.

This module computes numbers from whatever match files exist in
results/scored/ - it does not know or care whether those came from a real
experiment run or a single pilot generation. It is the caller's responsibility
not to present pilot-scale numbers as if they were the full-grid result.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCORED_DIR = REPO_ROOT / "results" / "scored"

# Per the 2026-07-19 decision recorded in corpus_manifest.csv (P-KHM/P-PAK/P-JOR/P-MAR
# rows) and paper draft Section III.A/F: these 4 documents have deliberately thin
# true registers (1-2 risks against a 8-9 category taxonomy) and are a targeted
# over-generation test for RQ3, not ordinary corpus rows. Their precision must be
# reported separately, never averaged into headline corpus-wide precision.
SHORT_REGISTER_SUBGROUP = {
    "P-KHM-BasicEducationImprovement",
    "P-PAK-ResilientAccessibleMicrofinance",
    "P-JOR-InnovativeStartupsSMEsFund2",
    "P-MAR-SecondIdentityTargetingSocialProtection",
    # Added 2026-07-19 (Madhu, via AskUserQuestion): UK SBC with the thinnest
    # register in the corpus - 3 one-line risk bullets, only 2 with a stated
    # mitigation, no likelihood/impact/rating of any kind. See
    # data/ground_truth/P-UK-FreeBreakfastClubs.json notes for full reasoning
    # and why P-UK-ConnectToWork was excluded outright instead of added here.
    "P-UK-FreeBreakfastClubs",
}


def run_metrics(match_result: dict) -> dict:
    """Compute recall/precision/category accuracy for a single scored run."""
    gen_risks = match_result["gen_risks"]
    gt_risks = match_result["gt_risks"]
    matches = match_result["matches"]

    precision = len(matches) / len(gen_risks) if gen_risks else None
    recall = len(matches) / len(gt_risks) if gt_risks else None
    category_hits = sum(1 for m in matches if m["category_agree"])
    category_accuracy = category_hits / len(matches) if matches else None

    matched_gt_ids = {m["gt_risk_id"] for m in matches}
    matched_gen_ids = {m["gen_risk_id"] for m in matches}
    missed = [r for r in gt_risks if r["risk_id"] not in matched_gt_ids]
    unsupported = [r for r in gen_risks if r["risk_id"] not in matched_gen_ids]

    return {
        "project_id": match_result.get("project_id"),
        "model": match_result.get("model"),
        "prompt_strategy": match_result.get("prompt_strategy"),
        "run_index": match_result.get("run_index"),
        "parse_failed": match_result.get("parse_failed", False),
        "n_generated": len(gen_risks),
        "n_ground_truth": len(gt_risks),
        "n_matched": len(matches),
        "precision": round(precision, 3) if precision is not None else None,
        "recall": round(recall, 3) if recall is not None else None,
        "category_accuracy_of_matches": round(category_accuracy, 3) if category_accuracy is not None else None,
        "missed_ground_truth_categories": [r["category"] for r in missed],
        "unsupported_generated_categories": [r["category"] for r in unsupported],
    }


def _safe_mean(values: list) -> Optional[float]:
    values = [v for v in values if v is not None]
    return round(mean(values), 3) if values else None


def aggregate_by_model_prompt(per_run: list[dict]) -> dict:
    """RQ2: how do results vary across models and prompting strategies."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in per_run:
        groups[(r["model"], r["prompt_strategy"])].append(r)

    out = {}
    for (model, prompt), runs in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        parse_failures = sum(1 for r in runs if r["parse_failed"])
        out[f"{model} / {prompt}"] = {
            "n_runs": len(runs),
            "n_parse_failed": parse_failures,
            "mean_recall": _safe_mean([r["recall"] for r in runs]),
            "mean_precision": _safe_mean([r["precision"] for r in runs]),
            "mean_category_accuracy": _safe_mean([r["category_accuracy_of_matches"] for r in runs]),
        }
    return out


def aggregate_by_category(per_run: list[dict]) -> dict:
    """RQ3: which categories are most often missed vs. hallucinated.

    'missed' = ground-truth risks in this category with no matching generated
    risk, pooled across every scored run. 'hallucinated' = generated risks in
    this category with no matching ground-truth risk, pooled the same way.
    These are raw counts, not rates - a category that appears rarely in the
    ground truth will mechanically have a small 'missed' count regardless of
    model quality, so pair this with per-category n from the ground truth
    corpus itself before drawing conclusions, not read off these counts alone.
    """
    missed_counts: dict[str, int] = defaultdict(int)
    hallucinated_counts: dict[str, int] = defaultdict(int)
    for r in per_run:
        for cat in r["missed_ground_truth_categories"]:
            missed_counts[cat] += 1
        for cat in r["unsupported_generated_categories"]:
            hallucinated_counts[cat] += 1

    categories = sorted(set(missed_counts) | set(hallucinated_counts))
    return {
        cat: {
            "missed_count": missed_counts.get(cat, 0),
            "hallucinated_count": hallucinated_counts.get(cat, 0),
        }
        for cat in categories
    }


def short_register_subgroup_report(per_run: list[dict]) -> dict:
    """Precision on the 5-document short-register subgroup, reported separately.

    Precision (not recall) is the number of interest here: a small true
    register is a sharp test of over-generation (RQ3), and averaging it into
    headline corpus precision would let a richer-register document's larger
    pool of legitimate targets mask this signal. See paper draft Section
    III.A/F.
    """
    subgroup_runs = [r for r in per_run if r["project_id"] in SHORT_REGISTER_SUBGROUP]
    by_project: dict[str, list[dict]] = defaultdict(list)
    for r in subgroup_runs:
        by_project[r["project_id"]].append(r)

    return {
        "n_runs": len(subgroup_runs),
        "mean_precision": _safe_mean([r["precision"] for r in subgroup_runs]),
        "mean_recall": _safe_mean([r["recall"] for r in subgroup_runs]),
        "by_project": {
            pid: {
                "n_runs": len(runs),
                "mean_precision": _safe_mean([r["precision"] for r in runs]),
                "mean_recall": _safe_mean([r["recall"] for r in runs]),
            }
            for pid, runs in sorted(by_project.items())
        },
    }


def compute_all(scored_dir: Path = SCORED_DIR) -> dict:
    match_files = sorted(p for p in scored_dir.glob("*.match.json"))
    if not match_files:
        raise FileNotFoundError(
            f"No *.match.json files found in {scored_dir} - run match.py first."
        )

    per_run = []
    for fp in match_files:
        with open(fp, encoding="utf-8") as f:
            match_result = json.load(f)
        per_run.append(run_metrics(match_result))

    corpus_wide = [r for r in per_run if r["project_id"] not in SHORT_REGISTER_SUBGROUP]

    return {
        "n_scored_runs_total": len(per_run),
        "n_parse_failed_total": sum(1 for r in per_run if r["parse_failed"]),
        "corpus_wide": {
            "n_runs": len(corpus_wide),
            "mean_recall": _safe_mean([r["recall"] for r in corpus_wide]),
            "mean_precision": _safe_mean([r["precision"] for r in corpus_wide]),
            "mean_category_accuracy": _safe_mean([r["category_accuracy_of_matches"] for r in corpus_wide]),
            "note": "Excludes the 5-document short-register subgroup - see short_register_subgroup block.",
        },
        "by_model_and_prompt": aggregate_by_model_prompt(per_run),
        "by_category": aggregate_by_category(per_run),
        "short_register_subgroup": short_register_subgroup_report(per_run),
        "per_run": per_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scored-dir",
        type=str,
        default=str(SCORED_DIR),
        help="Directory containing *.match.json files from match.py",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write the full report as JSON to this path (default: print to stdout only)",
    )
    args = parser.parse_args()

    try:
        report = compute_all(Path(args.scored_dir))
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # Print a compact summary; full per-run detail only goes to --out if given,
    # to keep stdout readable when this is run after a small number of runs.
    summary = {k: v for k, v in report.items() if k != "per_run"}
    print(json.dumps(summary, indent=2))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[metrics] full report (including per-run detail) written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
