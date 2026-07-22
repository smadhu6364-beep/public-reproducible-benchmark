"""gen_synthetic_kappa_demo.py - demonstrate compute_kappa.py's OUTPUT SHAPE
using entirely fabricated rater scores, so Madhu/Kruthik can see what a
Method B kappa report actually looks like before real raters exist to
produce one for real.

EVERYTHING THIS WRITES IS FAKE: the register codes, the "project" labels,
and every Likert score. Built entirely in memory (no CSVs written to disk,
matching gen_synthetic_cutoff_report.py's own "kept in memory, run straight
through the real function" approach) and run through the REAL
compute_kappa.compute_report() - same code path real ratings will use, not
a reimplementation of it.

Deliberately not degenerate: 3 fake raters with genuine (fabricated)
disagreement built in - not unanimous, not random noise - so the demo
actually shows kappa landing somewhere in the middle of the Landis & Koch
bands rather than trivially at 1.0 or undefined. 2 registers per (model x
prompt) cell, all 9 cells populated, so by_model/by_prompt_strategy both
show real (fabricated) 3-way and 3-way breakdowns instead of empty cells.

Output goes to scratch/synthetic_kappa_report.json (gitignored) - a
synthetic number must never be mistaken for a real result.

Usage:
  python analysis/gen_synthetic_kappa_demo.py
  python analysis/gen_synthetic_kappa_demo.py --out scratch/my_demo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))

import compute_kappa as ck  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "scratch" / "synthetic_kappa_report.json"

SYNTHETIC_WARNING = (
    "SYNTHETIC DEMONSTRATION ONLY. Every register code, project label, and "
    "Likert score below is fabricated for the sole purpose of showing what "
    "compute_kappa.py's report looks like. NONE of this is a real Method B "
    "finding. Do not cite, quote, or report any figure from this file as a "
    "real result."
)

# 2 fake registers per (model x prompt) cell = 18 total, mirroring
# rater_protocol.md section 3.1's real design (just smaller: 2/cell here
# instead of the real 5/cell) closely enough to exercise the same code
# paths (overall, by_model, by_prompt_strategy all populated).
_REGISTER_INDEX = 0


def _next_code() -> str:
    global _REGISTER_INDEX
    _REGISTER_INDEX += 1
    return f"SYN-{_REGISTER_INDEX:03d}"


def build_synthetic_blinding_map() -> dict[str, dict]:
    global _REGISTER_INDEX
    _REGISTER_INDEX = 0
    blinding_map = {}
    for model in ck.MODELS:
        for prompt in ck.PROMPTS:
            for i in range(2):
                code = _next_code()
                blinding_map[code] = {
                    "code": code,
                    "project_id": f"SYNTHETIC-PROJECT-{code}",
                    "model": model,
                    "prompt_strategy": prompt,
                    "run_index": "1",
                    "cell": f"{model}_{prompt}",
                }
    return blinding_map


def build_synthetic_ratings(blinding_map: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """3 fake raters with fabricated, deliberately-not-unanimous scores.
    Base score depends on model (so by_model differences show up in the
    demo output, the way a real between-model quality gap would), with a
    small deterministic per-rater offset (not random - reproducible without
    needing to seed anything) so raters disagree by 0-2 points, never wildly."""
    base_by_model = {"claude": 4, "gpt": 3, "opensource": 2}
    rater_offsets = {"rater_a": 0, "rater_b": -1, "rater_c": 1}

    ratings: dict[str, dict[str, dict]] = {r: {} for r in rater_offsets}
    for code, meta in blinding_map.items():
        base = base_by_model[meta["model"]]
        for rater_id, offset in rater_offsets.items():
            score = min(5, max(1, base + offset))
            ratings[rater_id][code] = {
                "completeness_1to5": score,
                "accuracy_1to5": min(5, max(1, score - 1 if meta["prompt_strategy"] == "structured" else score)),
                "actionability_1to5": score,
                "notable_issues": "SYNTHETIC placeholder note" if code.endswith("001") and rater_id == "rater_a" else "",
            }
    return ratings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    args = ap.parse_args()

    blinding_map = build_synthetic_blinding_map()
    ratings = build_synthetic_ratings(blinding_map)
    report = ck.compute_report(ratings, blinding_map)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = {"_SYNTHETIC_WARNING": SYNTHETIC_WARNING, **report}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    readme = out_path.parent / "_README_SYNTHETIC.txt"
    note = (
        "Includes synthetic_kappa_report.json from "
        "analysis/gen_synthetic_kappa_demo.py - fabricated register codes "
        "and Likert scores, run through the real compute_kappa.compute_report(). "
        "Gitignored (scratch/).\n"
    )
    if readme.exists():
        existing = readme.read_text(encoding="utf-8")
        if "synthetic_kappa_report.json" not in existing:
            readme.write_text(existing + note, encoding="utf-8")
    else:
        readme.write_text("SYNTHETIC pipeline-validation data - NOT real results.\n" + note, encoding="utf-8")

    print(f"[synth-kappa] wrote {out_path}", file=sys.stderr)
    print("[synth-kappa] REMINDER: every score above is fabricated - see docs/rater_protocol.md for the real protocol.", file=sys.stderr)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
