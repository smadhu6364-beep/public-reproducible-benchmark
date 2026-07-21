"""gen_synthetic_cutoff_report.py - demonstrate metrics.pretraining_cutoff_report()'s
OUTPUT SHAPE using entirely fabricated data, so Madhu/Kruthik can see what the report
actually looks like before real model_cutoffs exist to run it for real.

EVERYTHING THIS WRITES IS FAKE, INCLUDING THE CUTOFF DATES. Reuses
gen_synthetic_scored.py's existing synthetic match-record fixtures (same 2
projects, same fabricated recall/precision numbers - see that file's own
docstring for why those numbers are what they are) rather than duplicating
that logic, and pairs them with placeholder model_cutoffs dates that are
DELIBERATELY NOT the real published training-cutoff dates for these models
(see docs/model_cutoffs.md for those, researched separately and never
hardcoded into any code, per CLAUDE.md's no-fabrication rule and
pretraining_cutoff_report()'s own docstring). Mixing real cutoff dates into
an otherwise-100%-fabricated demo would be more misleading, not less - it
would dress up a fake result with one real-looking fact. Keeping the whole
demo obviously synthetic end to end avoids that.

The demo is deliberately not degenerate: reusing gen_synthetic_scored.py's
2 real project_ids means one (P-SRB-CompetitivenessJobs) has a real
publication_date in the actual corpus_manifest.csv (2015-07-23) and the
other (P-KHM-BasicEducationImprovement) does not - so this naturally
exercises all three of the report's buckets (pre_cutoff, post_cutoff, and
undated) using the REAL manifest's REAL publication_date gap, without this
script inventing manifest data of its own.

Output goes to scratch/synthetic_cutoff_report.json (gitignored, same as
gen_synthetic_scored.py's own output directory) - a synthetic number must
never be mistaken for a real result.

Usage:
  python analysis/gen_synthetic_cutoff_report.py
  python analysis/gen_synthetic_cutoff_report.py --out scratch/my_demo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics  # noqa: E402
from gen_synthetic_scored import GT, MODELS, PROMPTS, build_match_record  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "scratch" / "synthetic_cutoff_report.json"

# SYNTHETIC PLACEHOLDER DATES - NOT the real published training cutoffs for
# these models. Deliberately staggered (not all identical) so the demo
# actually exercises both pre_cutoff AND post_cutoff against
# P-SRB-CompetitivenessJobs's one real, populated publication_date
# (2015-07-23) rather than trivially dumping every run into the same
# bucket. See docs/model_cutoffs.md for the real, cited, researched dates -
# this script never reads that file and never should; the two are kept
# deliberately separate so a placeholder can never silently leak into a
# real analysis, or vice versa.
SYNTHETIC_PLACEHOLDER_MODEL_CUTOFFS = {
    "claude": "2020-06-01",       # placeholder: AFTER 2015-07-23 -> post_cutoff
    "gpt": "2010-06-01",          # placeholder: BEFORE 2015-07-23 -> pre_cutoff
    "opensource": "2020-06-01",   # placeholder: AFTER 2015-07-23 -> post_cutoff
}

SYNTHETIC_WARNING = (
    "SYNTHETIC DEMONSTRATION ONLY. Every number below - recall, precision, "
    "and the model_cutoffs_used dates themselves - is fabricated for the "
    "sole purpose of showing what metrics.pretraining_cutoff_report()'s "
    "output looks like. NONE of this is a real finding about contamination, "
    "and the cutoff dates are NOT the real published training cutoffs for "
    "these models (see docs/model_cutoffs.md for those). Do not cite, quote, "
    "or report any figure from this file as a real result."
)


def build_synthetic_per_run(runs_per_cell: int = 2) -> list[dict]:
    """Same fixture-building logic gen_synthetic_scored.py's main() uses to
    write *.match.json files, but kept in memory and run straight through
    metrics.run_metrics() - this demo only needs the per_run list
    pretraining_cutoff_report() consumes, not files on disk."""
    per_run = []
    for project_id in GT:
        for model in MODELS:
            for prompt in PROMPTS:
                for run_index in range(1, runs_per_cell + 1):
                    match_record = build_match_record(project_id, model, prompt, run_index)
                    per_run.append(metrics.run_metrics(match_record))
    return per_run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    ap.add_argument("--runs", type=int, default=2, help="Runs per (project, model, prompt) cell (default 2, matches gen_synthetic_scored.py's default)")
    args = ap.parse_args()

    per_run = build_synthetic_per_run(args.runs)
    report = metrics.pretraining_cutoff_report(
        per_run,
        SYNTHETIC_PLACEHOLDER_MODEL_CUTOFFS,
        manifest_path=metrics.REPO_ROOT / "data" / "corpus_manifest.csv",
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = {"_SYNTHETIC_WARNING": SYNTHETIC_WARNING, **report}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    readme = out_path.parent / "_README_SYNTHETIC.txt"
    if not readme.exists():
        readme.write_text(
            "SYNTHETIC pipeline-validation data - NOT real results.\n"
            "Includes synthetic_cutoff_report.json from "
            "analysis/gen_synthetic_cutoff_report.py - fabricated recall/"
            "precision AND fabricated placeholder cutoff dates. Gitignored "
            "(scratch/). See docs/model_cutoffs.md for the real researched "
            "cutoff dates, kept deliberately separate from this file.\n",
            encoding="utf-8",
        )

    print(f"[synth-cutoff] wrote {out_path}", file=sys.stderr)
    print("[synth-cutoff] REMINDER: fabricated data AND fabricated cutoff dates - see docs/model_cutoffs.md for the real ones.", file=sys.stderr)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
