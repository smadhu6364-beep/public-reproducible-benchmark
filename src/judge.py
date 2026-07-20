"""judge.py - LLM-as-judge scoring (SUPPLEMENTARY evaluation only, Method C).

IMPLEMENTED 2026-07-19 with explicit user approval, after the project's own
10-document ground-truth validation gate was crossed (18/18 non-set-aside
documents). Method C is supplementary: primary evaluation is (A) semantic
matching (match.py/metrics.py) and (B) expert Likert ratings with Fleiss'
kappa (not yet implemented - human protocol, see HANDOFF_VSCODE_SESSION.md).
Per the evaluation-methodology literature cited in the paper draft (Section
II.C - LLM-as-judge reliability is documented as unstable across near-
identical prompts, systematically biased, and poorly calibrated in
domain-specific settings), judge.py's output is reported STRICTLY as a
correlation against Method B human ratings once those exist. It must never
stand in for Method A or Method B, and no discussion/results section should
cite a judge.py score as if it were an independent quality measure.

Rubric: deliberately the SAME three dimensions requested from Method B's
rater protocol (completeness, accuracy, actionability of mitigations, each
1-5, plus an overall 1-5) so that a later correlation calculation compares
like with like. If the human rater protocol ends up using different
dimensions, this rubric must be updated to match before any correlation is
computed - a judge score on a different scale than the human rating it's
meant to correlate against is not usable.

Leakage: the judge sees the SAME evidence a human Method B rater would see -
the generated risk register plus the project's planning documentation - and
NEVER the ground-truth register, for the same reason models never see it.
This module does not import GROUND_TRUTH_DIR from run_experiments.py and does
not read anything under data/ground_truth/ or data/risk_source_audit/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_OUTPUTS_DIR = REPO_ROOT / "results" / "raw_outputs"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
SCORED_DIR = REPO_ROOT / "results" / "scored"

# Which model acts as judge is itself a design choice worth stating plainly
# rather than defaulting silently: using one of the three models under test to
# judge its own (or a competitor's) output risks self-preference bias, a
# specific, documented failure mode of LLM-as-judge setups. JUDGE_MODEL_NAME
# should be set in .env to a model NOT among the three being benchmarked, or
# if that's not practical, the paper must disclose which judge model was used
# and discuss this as a limitation.
JUDGE_RUBRIC_PROMPT = """You are an expert reviewer of project risk registers. You will be shown a
project's planning documentation and a risk register generated for that
project. Score the register on three dimensions, each on a 1-5 scale (1 =
poor, 5 = excellent), using ONLY the planning documentation provided as your
basis for judging what risks a good register for this project should contain
- you do not have access to any other reference register:

  - completeness: does the register cover the material risks evident in the
    planning documentation, without major gaps?
  - accuracy: are the identified risks actually grounded in and consistent
    with the planning documentation (not invented, not contradicted by it)?
  - actionability: are the proposed mitigations concrete and specific enough
    that a project team could act on them, rather than generic platitudes?

Output ONLY a single JSON object, no prose, no markdown fences, in exactly
this form:
{"completeness": <1-5 integer>, "accuracy": <1-5 integer>, "actionability": <1-5 integer>, "overall": <1-5 integer>, "rationale": "<one or two sentences>"}

PROJECT PLANNING DOCUMENTATION:
\"\"\"
{{PLANNING_DOCUMENT}}
\"\"\"

GENERATED RISK REGISTER TO SCORE:
\"\"\"
{{GENERATED_REGISTER_JSON}}
\"\"\"

Return the JSON object now.
"""

_JUDGE_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def render_judge_prompt(planning_text: str, generated_register: dict) -> str:
    return (
        JUDGE_RUBRIC_PROMPT.replace("{{PLANNING_DOCUMENT}}", planning_text)
        .replace("{{GENERATED_REGISTER_JSON}}", json.dumps(generated_register, indent=2))
    )


def parse_judge_response(raw_text: str) -> tuple[Optional[dict], Optional[str]]:
    text = raw_text.strip()
    fence_stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(fence_stripped)
    except json.JSONDecodeError:
        m = _JUDGE_JSON_RE.search(fence_stripped)
        if not m:
            return None, "no JSON object found in judge response"
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return None, f"JSON parse failed: {e}"

    required = {"completeness", "accuracy", "actionability", "overall"}
    missing = required - set(parsed)
    if missing:
        return None, f"judge response missing required fields: {sorted(missing)}"
    for field in required:
        v = parsed[field]
        # bool is a subclass of int in Python (isinstance(True, int) is True),
        # so a stray {"completeness": true, ...} would otherwise silently pass
        # as a score of 1 - explicitly excluded here, found via a hand-built
        # adversarial-input test (see the parse_judge_response test pass).
        if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 5):
            return None, f"judge field {field!r} must be an integer 1-5, got {v!r}"

    return parsed, None


def judge_one(raw_output_path: Path, call_judge_model) -> dict:
    """call_judge_model: a callable(prompt: str) -> str, e.g. a partial of
    run_experiments.call_claude/call_gpt with model/temperature/max_tokens
    already bound. Kept as an injected callable (rather than importing a
    specific provider call here) so this module doesn't hardcode which
    provider acts as judge - see JUDGE_MODEL_NAME note above."""
    with open(raw_output_path, encoding="utf-8") as f:
        run_record = json.load(f)

    project_id = run_record["project_id"]
    generated = run_record.get("parsed_risks")

    result = {
        "run_file": raw_output_path.name,
        "project_id": project_id,
        "generation_model": run_record.get("model"),
        "generation_prompt_strategy": run_record.get("prompt_strategy"),
        "generation_run_index": run_record.get("run_index"),
    }

    if generated is None:
        result.update({"judged": False, "reason": "underlying generation had no parseable risks (parse_failed)"})
        return result

    planning_path = PROCESSED_DIR / f"{project_id}.txt"
    planning_text = planning_path.read_text(encoding="utf-8")

    prompt = render_judge_prompt(planning_text, generated)
    raw_judge_text = call_judge_model(prompt)
    scores, error = parse_judge_response(raw_judge_text)

    result.update(
        {
            "judged": scores is not None,
            "scores": scores,
            "parse_error": error,
            "raw_judge_response": raw_judge_text,
        }
    )
    return result


def _default_judge_caller():
    """Builds a call_judge_model callable from .env config, reusing
    run_experiments.py's provider wrappers rather than duplicating them."""
    import os
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_experiments as re_mod

    judge_model_label = os.environ.get("JUDGE_MODEL_LABEL", "claude")
    if judge_model_label not in re_mod.MODEL_DISPATCH:
        raise RuntimeError(f"JUDGE_MODEL_LABEL={judge_model_label!r} must be one of {list(re_mod.MODEL_DISPATCH)}")
    model_version = re_mod.resolve_model_version(judge_model_label)
    call_fn = re_mod.MODEL_DISPATCH[judge_model_label]

    def _call(prompt: str) -> str:
        return call_fn(prompt, model_version, temperature=0.0, max_tokens=512)

    return _call


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="Judge every file in results/raw_outputs/")
    parser.add_argument("--file", type=str, help="Judge a single raw_outputs/ file")
    parser.add_argument("--out-dir", type=str, default=str(SCORED_DIR))
    args = parser.parse_args()

    if not args.all and not args.file:
        parser.error("Specify --all or --file <path>")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        targets = [Path(args.file)]
    else:
        targets = sorted(p for p in RAW_OUTPUTS_DIR.glob("*.json") if p.name != ".gitkeep")

    if not targets:
        print(f"No raw output files found in {RAW_OUTPUTS_DIR}", file=sys.stderr)
        sys.exit(1)

    call_judge_model = _default_judge_caller()

    for raw_path in targets:
        result = judge_one(raw_path, call_judge_model)
        out_path = out_dir / (raw_path.stem + ".judge.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        status = "OK" if result["judged"] else f"SKIPPED ({result.get('reason') or result.get('parse_error')})"
        print(f"[judge] {raw_path.name} -> {status}")
        print(f"  -> wrote {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
