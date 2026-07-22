"""gen_synthetic_scored.py - synthetic *.match.json fixtures for pipeline validation ONLY.

Task C requires exercising the real match.py -> metrics.py -> figures chain, but no
real experiment has run yet (no API keys). This generator fabricates match.json-shaped
files - the exact schema match.py.score_raw_output() writes and metrics.py consumes -
so metrics.py and analysis/make_figures.py can be tested end to end against a
representative slice of the real 3-model x 3-prompt grid.

EVERYTHING THIS WRITES IS FAKE. Output goes to scratch/synthetic_scored/ (gitignored)
so a synthetic number can never be mistaken for a real result. Numbers here are
hand-designed to make the figures non-degenerate (spread across models/prompts, real
misses/hallucinations/category-disagreements, an "other"-category ground-truth risk,
and a parse_failed run) - they are NOT predictions of how any model will actually do.

Deterministic: the same run produces the same files.

Scenario (2 projects, both real project_ids so downstream subgroup logic engages):
  - P-KHM-BasicEducationImprovement: a SHORT_REGISTER_SUBGROUP project (metrics.py) -
    1 ground-truth risk, models over-generate (the RQ3 over-generation test). Precision
    is structurally low here; reported separately, never pooled into corpus_wide.
  - P-SRB-CompetitivenessJobs: an ordinary project - 6 ground-truth risks spanning
    several categories, including one category="other" risk (only ground truth can be
    "other"; the output schema forbids it for generated risks - so "other" always shows
    hallucinated_count=0 downstream, which is correct, not missing data).

Skill is varied so RQ2 is legible: claude > gpt > opensource, structured > few_shot >
zero_shot. Weaker cells match fewer ground-truth risks and hallucinate more; the
weakest cell on the short project (opensource/zero_shot) is a parse failure.

Usage:
  python analysis/gen_synthetic_scored.py                 # -> scratch/synthetic_scored/
  python analysis/gen_synthetic_scored.py --runs 2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "scratch" / "synthetic_scored"

MODELS = ["claude", "gpt", "opensource"]
PROMPTS = ["zero_shot", "few_shot", "structured"]

MODEL_SKILL = {"claude": 1.0, "gpt": 0.82, "opensource": 0.58}
PROMPT_SKILL = {"zero_shot": 0.72, "few_shot": 0.86, "structured": 1.0}

# Synthetic ground-truth registers (FAKE categories, chosen for coverage).
GT = {
    "P-KHM-BasicEducationImprovement": [
        {"risk_id": "G01", "category": "environmental"},
    ],
    "P-SRB-CompetitivenessJobs": [
        {"risk_id": "G01", "category": "political_regulatory"},
        {"risk_id": "G02", "category": "external"},
        {"risk_id": "G03", "category": "financial"},
        {"risk_id": "G04", "category": "organizational"},
        {"risk_id": "G05", "category": "technical"},
        {"risk_id": "G06", "category": "other"},  # only ground truth can be "other"
    ],
}

# Categories a generated risk can take (output_schema.json enum - NO "other").
GEN_CATEGORIES = [
    "technical", "financial", "schedule", "stakeholder",
    "political_regulatory", "environmental", "organizational", "external",
]


def _fake_desc(cat: str, tag: str) -> str:
    return f"[SYNTHETIC] {tag} risk in the {cat} category (fabricated for pipeline validation)."


def build_match_record(project_id: str, model: str, prompt: str, run_index: int) -> dict:
    """Construct one synthetic scored-run record in match.py.score_raw_output() shape."""
    gt_risks = [dict(r) for r in GT[project_id]]
    n_gt = len(gt_risks)
    skill = MODEL_SKILL[model] * PROMPT_SKILL[prompt]

    run_bump = (run_index - 1)  # run2 hallucinates one extra, to make aggregation non-trivial

    # --- parse-failure case: weakest cell on the short project ---
    if project_id == "P-KHM-BasicEducationImprovement" and model == "opensource" and prompt == "zero_shot":
        return {
            "run_file": f"{project_id}__{model}__{prompt}__run{run_index}.json",
            "project_id": project_id, "model": model, "prompt_strategy": prompt,
            "run_index": run_index, "parse_failed": True,
            "embedding_model": None, "threshold": 0.45,
            "matches": [], "gen_risks": [], "gt_risks": gt_risks,
        }

    matches = []
    gen_risks = []
    gen_counter = 0

    if project_id == "P-KHM-BasicEducationImprovement":
        # Over-generation test: model emits several risks; matches the 1 GT only if skilled.
        n_gen = 3 + run_bump  # 3-4 generated risks against 1 real risk
        matched_gt = 1 if skill >= 0.5 else 0
        for i in range(n_gen):
            gen_counter += 1
            gid = f"S{gen_counter:02d}"
            if i == 0 and matched_gt:
                # match G01 (environmental); a weak cell disagrees on category
                gen_cat = "environmental" if skill >= 0.7 else "organizational"
                gen_risks.append({"risk_id": gid, "category": gen_cat,
                                  "description": _fake_desc(gen_cat, "matched")})
                matches.append({
                    "gen_risk_id": gid, "gt_risk_id": "G01",
                    "similarity": round(0.55 + 0.2 * skill, 3),
                    "gen_category": gen_cat, "gt_category": "environmental",
                    "category_agree": gen_cat == "environmental",
                })
            else:
                hcat = GEN_CATEGORIES[(gen_counter + i) % len(GEN_CATEGORIES)]
                gen_risks.append({"risk_id": gid, "category": hcat,
                                  "description": _fake_desc(hcat, "hallucinated")})
        return _record(project_id, model, prompt, run_index, matches, gen_risks, gt_risks)

    # --- ordinary project (SRB, 6 GT risks) ---
    n_match = max(1, round(n_gt * skill))              # skilled cells match more GT risks
    n_match = min(n_match, n_gt)
    n_hallucinate = max(0, round((1 - skill) * 3)) + run_bump
    # Which GT risks get matched: take the first n_match (deterministic).
    for gi in range(n_match):
        gen_counter += 1
        gid = f"S{gen_counter:02d}"
        gt = gt_risks[gi]
        # A minority of matches disagree on category; the "other" GT risk ALWAYS
        # disagrees (generated risks can't be "other").
        if gt["category"] == "other":
            gen_cat = "organizational"
        elif skill < 0.65 and gi == n_match - 1:
            gen_cat = "stakeholder" if gt["category"] != "stakeholder" else "schedule"
        else:
            gen_cat = gt["category"]
        gen_risks.append({"risk_id": gid, "category": gen_cat,
                          "description": _fake_desc(gen_cat, "matched")})
        matches.append({
            "gen_risk_id": gid, "gt_risk_id": gt["risk_id"],
            "similarity": round(0.5 + 0.25 * skill, 3),
            "gen_category": gen_cat, "gt_category": gt["category"],
            "category_agree": gen_cat == gt["category"],
        })
    for h in range(n_hallucinate):
        gen_counter += 1
        gid = f"S{gen_counter:02d}"
        hcat = GEN_CATEGORIES[(gi + h + 1) % len(GEN_CATEGORIES)] if n_match else GEN_CATEGORIES[h % len(GEN_CATEGORIES)]
        gen_risks.append({"risk_id": gid, "category": hcat,
                          "description": _fake_desc(hcat, "hallucinated")})
    return _record(project_id, model, prompt, run_index, matches, gen_risks, gt_risks)


def _record(project_id, model, prompt, run_index, matches, gen_risks, gt_risks) -> dict:
    return {
        "run_file": f"{project_id}__{model}__{prompt}__run{run_index}.json",
        "project_id": project_id, "model": model, "prompt_strategy": prompt,
        "run_index": run_index, "parse_failed": False,
        "embedding_model": "all-MiniLM-L6-v2 [SYNTHETIC]", "threshold": 0.45,
        "matches": matches, "gen_risks": gen_risks, "gt_risks": gt_risks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=2, help="Runs per (project, model, prompt) cell (default 2)")
    ap.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT))
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # Clear any prior synthetic files so stale runs don't accumulate.
    for old in out.glob("*.match.json"):
        old.unlink()

    n = 0
    for project_id in GT:
        for model in MODELS:
            for prompt in PROMPTS:
                for run_index in range(1, args.runs + 1):
                    rec = build_match_record(project_id, model, prompt, run_index)
                    fname = f"{project_id}__{model}__{prompt}__run{run_index}.match.json"
                    (out / fname).write_text(json.dumps(rec, indent=2), encoding="utf-8")
                    n += 1

    readme = (
        "SYNTHETIC pipeline-validation data - NOT real results.\n"
        "Generated by analysis/gen_synthetic_scored.py to exercise metrics.py -> figures.\n"
        "Every number here is fabricated. Gitignored (scratch/).\n"
    )
    (out / "_README_SYNTHETIC.txt").write_text(readme, encoding="utf-8")

    print(f"[synth] wrote {n} synthetic *.match.json files to {out}")
    print(f"[synth] projects={list(GT)}, models={MODELS}, prompts={PROMPTS}, runs={args.runs}")
    print("[synth] REMINDER: fabricated data for pipeline validation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
