"""compute_kappa.py - Method B: Fleiss' kappa + mean Likert scores from
completed rater assignment sheets.

Task G1. Closes the one gap docs/rater_protocol.md section 4 explicitly
flagged as "Not yet built": a results -> kappa computation script. Everything
below implements that section's spec directly - read it first if a
methodology question comes up ("why per-dimension, not pooled", "why 5
categories not 3", "why full overlap required").

INPUT CONTRACT (produced by src/build_rater_packets.py):
  - results/rater_packets/blinding_map.csv - code -> project_id/model/
    prompt_strategy/run_index (GITIGNORED - never shown to raters, only used
    here, after all ratings are in, to break results out by model/prompt).
  - results/rater_packets/rater_assignments/<rater_id>.csv - one per rater,
    columns packet_code, completeness_1to5, accuracy_1to5,
    actionability_1to5, notable_issues. build_rater_packets.py writes these
    with blank score columns; a completed sheet is the same file with the
    three score columns filled in by a rater. This script reads *completed*
    sheets from --assignments-dir (default: the same rater_assignments/
    directory - a rater's returned sheet is expected to land back there,
    overwriting the blank template it started as).

DESIGN, per rater_protocol.md section 4:
  - Kappa is computed SEPARATELY per Likert dimension (Completeness,
    Accuracy, Actionability) - three values, not one pooled score.
  - Each of the 5 Likert points is treated as a nominal category (Fleiss'
    kappa's standard use, not an ordinal-aware statistic) - a known
    simplification, stated as such in the paper's methodology section, not
    hidden here.
  - Reported three ways: overall (all rated registers), by model, by prompt
    strategy - mirroring metrics.py's Method A subgroup structure so the
    paper's Method A/B tables read as one consistent analysis.
  - Mean Likert scores are reported alongside kappa for every breakout -
    kappa says whether raters agree, the mean says what they agreed about.
  - The full-overlap design (every rater scores every sampled register) is
    a precondition, not an assumption to paper over: if the loaded sheets
    don't actually cover the same code set, this fails loudly with the
    specific rater/code gap named, rather than silently computing kappa
    over whatever partial overlap happens to exist.

IMPLEMENTATION NOTE - why not scipy.stats or statsmodels: rater_protocol.md
section 4 names both as having Fleiss' kappa implementations. Neither is
currently pinned in requirements.txt, and CLAUDE.md requires asking before
adding a new dependency. The formula itself (Fleiss 1971) is short,
well-defined, and implemented directly below with numpy (already pinned) -
more transparent for a paper's methodology section than an opaque library
call, and verified against an independently-computed worked example in
tests/test_compute_kappa.py rather than trusted on inspection alone.

CITATIONS: Fleiss, J.L. (1971). "Measuring nominal scale agreement among
many raters." Psychological Bulletin, 76(5), 378-382 - the kappa formula.
Landis, J.R. & Koch, G.G. (1977). "The measurement of observer agreement
for categorical data." Biometrics, 33(1), 159-174 - the interpretation
bands below. Both already cited in docs/lit_review_foundation.md Theme 5.

Run:
  python src/compute_kappa.py
  python src/compute_kappa.py --assignments-dir path/to/completed --out results/kappa_report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
RATER_PACKETS_DIR = REPO_ROOT / "results" / "rater_packets"
BLINDING_MAP_PATH = RATER_PACKETS_DIR / "blinding_map.csv"
ASSIGNMENTS_DIR = RATER_PACKETS_DIR / "rater_assignments"

# Column name -> human label, in the fixed order rater_protocol.md section 4
# reports them.
DIMENSIONS = {
    "completeness_1to5": "Completeness",
    "accuracy_1to5": "Accuracy/Plausibility",
    "actionability_1to5": "Actionability of Mitigations",
}
CATEGORIES = [1, 2, 3, 4, 5]  # the fixed 1-5 Likert scale, treated as nominal.

MODELS = ["claude", "gpt", "opensource"]
PROMPTS = ["zero_shot", "few_shot", "structured"]


def _show(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(Path(path).resolve())


def load_blinding_map(path: Path) -> dict[str, dict]:
    """code -> {project_id, model, prompt_strategy, run_index, cell}"""
    if not path.exists():
        raise FileNotFoundError(
            f"Blinding map not found at {path} - run "
            f"src/build_rater_packets.py first (it writes this file)."
        )
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["code"]] = row
    return out


def load_rater_assignments(assignments_dir: Path) -> dict[str, dict[str, dict]]:
    """rater_id (derived from filename) -> {code -> {dimension_col: int, notable_issues: str}}.

    Raises ValueError, naming the exact file/row, on a non-blank score that
    doesn't parse as an integer 1-5 - a typo here should stop the run, not
    get silently coerced or dropped.
    """
    if not assignments_dir.is_dir():
        raise FileNotFoundError(f"No rater assignments directory at {assignments_dir}")
    files = sorted(assignments_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No *.csv files found in {assignments_dir}")

    all_ratings: dict[str, dict[str, dict]] = {}
    for fp in files:
        rater_id = fp.stem
        with open(fp, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"packet_code", "completeness_1to5", "accuracy_1to5", "actionability_1to5"}
            missing_cols = required - set(reader.fieldnames or [])
            if missing_cols:
                raise ValueError(f"{fp.name}: missing expected column(s) {sorted(missing_cols)}")
            rater_rows: dict[str, dict] = {}
            for row in reader:
                code = row["packet_code"].strip()
                if not code:
                    continue
                parsed = {}
                for col in DIMENSIONS:
                    raw = (row.get(col) or "").strip()
                    if not raw:
                        raise ValueError(
                            f"{fp.name}, packet {code}: {col} is blank - this "
                            f"rater's sheet isn't fully completed yet. Every "
                            f"rater must score every register (full-overlap "
                            f"design, rater_protocol.md section 3.1) before "
                            f"kappa can be computed."
                        )
                    try:
                        value = int(raw)
                    except ValueError:
                        raise ValueError(
                            f"{fp.name}, packet {code}: {col}={raw!r} is not "
                            f"an integer."
                        )
                    if value not in CATEGORIES:
                        raise ValueError(
                            f"{fp.name}, packet {code}: {col}={value} is "
                            f"outside the 1-5 scale."
                        )
                    parsed[col] = value
                parsed["notable_issues"] = (row.get("notable_issues") or "").strip()
                rater_rows[code] = parsed
        all_ratings[rater_id] = rater_rows
    return all_ratings


def validate_full_overlap(ratings: dict[str, dict[str, dict]]) -> list[str]:
    """Every rater must have scored the exact same set of codes (section 3.1's
    full-overlap design is a precondition for the kappa computation below,
    not just a sampling nicety). Returns the shared sorted code list, or
    raises ValueError naming which rater/codes disagree."""
    rater_ids = sorted(ratings)
    if len(rater_ids) < 2:
        raise ValueError(
            f"Fleiss' kappa needs at least 2 raters; found {len(rater_ids)} "
            f"completed sheet(s) in the assignments directory."
        )
    code_sets = {r: set(ratings[r]) for r in rater_ids}
    union = set.union(*code_sets.values())
    for r in rater_ids:
        missing = sorted(union - code_sets[r])
        if missing:
            raise ValueError(
                f"Full-overlap design violated: rater {r!r} is missing "
                f"{len(missing)} code(s) that at least one other rater has, "
                f"e.g. {missing[:5]}. Every rater must score every sampled "
                f"register (rater_protocol.md section 3.1) before kappa is "
                f"meaningful."
            )
    return sorted(union)


def fleiss_kappa(category_counts: np.ndarray) -> float:
    """Standard Fleiss (1971) kappa. category_counts is an (N subjects, k
    categories) matrix of how many raters assigned each category to each
    subject. Requires the same number of raters n for every subject (the
    fully-crossed design this project uses) - see validate_full_overlap().

    Returns nan when P_e_bar == 1 (every rating fell in exactly one
    category, chance agreement is undefined/total) rather than raising
    ZeroDivisionError - this is a real, reportable "no variance to measure
    agreement over" state, not a bug.
    """
    N, k = category_counts.shape
    n_per_subject = category_counts.sum(axis=1)
    if not np.all(n_per_subject == n_per_subject[0]):
        raise ValueError(
            "fleiss_kappa requires the same number of raters for every "
            "subject - got varying row totals: "
            f"{sorted(set(n_per_subject.tolist()))}"
        )
    n = int(n_per_subject[0])
    if n < 2:
        raise ValueError(f"fleiss_kappa needs at least 2 raters per subject, got {n}")

    P_i = (np.sum(category_counts ** 2, axis=1) - n) / (n * (n - 1))
    P_bar = float(P_i.mean())
    p_j = category_counts.sum(axis=0) / (N * n)
    P_e_bar = float(np.sum(p_j ** 2))
    if P_e_bar >= 1.0:
        return float("nan")
    return (P_bar - P_e_bar) / (1 - P_e_bar)


def interpretation_band(kappa: float) -> str:
    """Landis & Koch (1977) standard bands."""
    if kappa is None or (isinstance(kappa, float) and np.isnan(kappa)):
        return "undefined (no rating variance)"
    if kappa < 0:
        return "poor"
    if kappa <= 0.20:
        return "slight"
    if kappa <= 0.40:
        return "fair"
    if kappa <= 0.60:
        return "moderate"
    if kappa <= 0.80:
        return "substantial"
    return "almost perfect"


def _category_matrix(codes: list[str], ratings: dict[str, dict[str, dict]], dimension: str) -> np.ndarray:
    rater_ids = sorted(ratings)
    matrix = np.zeros((len(codes), len(CATEGORIES)), dtype=int)
    for i, code in enumerate(codes):
        for rater_id in rater_ids:
            value = ratings[rater_id][code][dimension]
            matrix[i, CATEGORIES.index(value)] += 1
    return matrix


def _mean_score(codes: list[str], ratings: dict[str, dict[str, dict]], dimension: str) -> float:
    values = [ratings[rater_id][code][dimension] for rater_id in ratings for code in codes]
    return float(np.mean(values)) if values else float("nan")


def _dimension_block(codes: list[str], ratings: dict[str, dict[str, dict]], dimension: str) -> dict:
    matrix = _category_matrix(codes, ratings, dimension)
    kappa = fleiss_kappa(matrix)
    return {
        "kappa": None if np.isnan(kappa) else round(kappa, 4),
        "interpretation": interpretation_band(kappa),
        "mean_score": round(_mean_score(codes, ratings, dimension), 4),
        "n_registers": len(codes),
        "n_raters": len(ratings),
    }


def compute_report(ratings: dict[str, dict[str, dict]], blinding_map: dict[str, dict]) -> dict:
    all_codes = validate_full_overlap(ratings)
    unmapped = sorted(set(all_codes) - set(blinding_map))
    if unmapped:
        raise ValueError(
            f"{len(unmapped)} rated code(s) have no entry in the blinding "
            f"map, e.g. {unmapped[:5]} - blinding_map.csv and the rater "
            f"assignment sheets have drifted out of sync."
        )

    report: dict = {
        "n_registers_rated": len(all_codes),
        "n_raters": len(ratings),
        "rater_ids": sorted(ratings),
        "overall": {},
        "by_model": {},
        "by_prompt_strategy": {},
        "notable_issues": [],
    }

    for col, label in DIMENSIONS.items():
        report["overall"][label] = _dimension_block(all_codes, ratings, col)

    for model in MODELS:
        codes = [c for c in all_codes if blinding_map[c]["model"] == model]
        report["by_model"][model] = {
            DIMENSIONS[col]: _dimension_block(codes, ratings, col) for col in DIMENSIONS
        } if codes else {"note": "no rated registers for this model"}

    for prompt in PROMPTS:
        codes = [c for c in all_codes if blinding_map[c]["prompt_strategy"] == prompt]
        report["by_prompt_strategy"][prompt] = {
            DIMENSIONS[col]: _dimension_block(codes, ratings, col) for col in DIMENSIONS
        } if codes else {"note": "no rated registers for this prompt strategy"}

    # Free text feeds RQ3 (rater_protocol.md section 2) - collected, not
    # scored. One entry per (rater, code) with a non-empty note.
    for rater_id in sorted(ratings):
        for code in all_codes:
            note = ratings[rater_id][code].get("notable_issues", "")
            if note:
                meta = blinding_map.get(code, {})
                report["notable_issues"].append({
                    "rater_id": rater_id,
                    "code": code,
                    "project_id": meta.get("project_id"),
                    "model": meta.get("model"),
                    "prompt_strategy": meta.get("prompt_strategy"),
                    "note": note,
                })

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assignments-dir", type=str, default=str(ASSIGNMENTS_DIR),
                         help="Directory of completed rater_id.csv sheets (default: results/rater_packets/rater_assignments/)")
    parser.add_argument("--blinding-map", type=str, default=str(BLINDING_MAP_PATH),
                         help="Path to blinding_map.csv (default: results/rater_packets/blinding_map.csv)")
    parser.add_argument("--out", type=str, default=None,
                         help="Write the full report as JSON to this path (default: print to stdout only)")
    args = parser.parse_args()

    try:
        ratings = load_rater_assignments(Path(args.assignments_dir))
        blinding_map = load_blinding_map(Path(args.blinding_map))
        report = compute_report(ratings, blinding_map)
    except (FileNotFoundError, ValueError) as e:
        print(f"[compute_kappa] {e}", file=sys.stderr)
        return 1

    print(json.dumps({k: v for k, v in report.items() if k != "notable_issues"}, indent=2))
    print(f"\n[compute_kappa] {len(report['notable_issues'])} notable-issues note(s) collected (see --out for full text).", file=sys.stderr)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[compute_kappa] full report written to {_show(out_path)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
