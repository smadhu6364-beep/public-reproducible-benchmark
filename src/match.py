"""match.py - semantic matching of generated risks against ground truth (Method A, primary).

IMPLEMENTED 2026-07-19 with explicit user approval, after the project's own
10-document ground-truth validation gate was crossed (18/18 non-set-aside
documents, not merely 10). Supersedes scratch/match_metrics_prototype.py, which
used TF-IDF cosine similarity as a deliberately simple discussion draft; this
file uses sentence-transformer embeddings as that prototype's own docstring
said the real implementation should.

Responsibilities:
  - Embed generated and ground-truth risk descriptions+mitigations
    (sentence-transformers).
  - Match generated risks to ground-truth risks, per project, above a
    similarity threshold (greedy, highest-similarity-first, one-to-one).
  - Emit per-run match tables into results/scored/ for metrics.py to consume.

Known limitations, stated plainly rather than hidden:
  - MATCH_THRESHOLD was 0.5 as a first-pass default; on 2026-07-20 it was
    lowered to 0.45 after validation against a hand-labeled pair set (see
    src/validate_threshold.py and results/threshold_validation_report.md).
    That validation is NOT a substitute for tuning against a real experiment
    run: its "generated" side is hand-written to emulate model output because
    no real output exists yet (no API keys). It is a realistic labeled
    sample, not a harvested one. EMBEDDING_MODEL (all-MiniLM-L6-v2) validated
    as fit for purpose in the same run (clean separation of should-match vs.
    should-not-match pairs). Treat any recall/precision numbers produced
    before the threshold is re-checked against a real run as provisional, and
    say so in the paper if it is not revisited before real numbers are
    reported.
  - Generated risks can never have category="other" (forbidden by
    prompts/output_schema.json's enum), but ground-truth risks sometimes do
    (e.g. a SORT "Other" row narrated as a distinct risk). A generated risk
    that correctly matches the SUBSTANCE of an "other"-categorized ground
    truth risk will therefore always show category_agree=False. This is a
    structural artifact of the two schemas, not a scoring bug - do not read
    0% category accuracy on "other" as a model failure.
  - Matching is strictly within-project. A generated risk is only ever
    compared to the same project's ground truth, never across projects -
    doing otherwise would silently reintroduce the leakage the rest of the
    pipeline is built to prevent.
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
GROUND_TRUTH_DIR = REPO_ROOT / "data" / "ground_truth"
SCORED_DIR = REPO_ROOT / "results" / "scored"

# See "Known limitations" above. Override via CLI flags for any
# tuning/sensitivity-analysis pass rather than editing these in place, so the
# default stays visible in version control.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# Validated 2026-07-20 (src/validate_threshold.py, results/threshold_validation_report.md).
# On the hand-labeled clean pairs, should-match similarities ranged 0.52-0.81
# (mean 0.66) and should-NOT-match 0.20-0.42 (mean 0.28) - cleanly separable,
# gap (0.42, 0.52), midpoint 0.47. Both 0.45 and 0.50 classify the clean set
# perfectly, but 0.45 was chosen over the prior 0.50 because: (a) the lowest
# true-positive similarity was 0.52, leaving 0.50 only a 0.02 margin against
# real-output noise, vs. 0.07 at 0.45; (b) on the realistic granularity-
# mismatch task (a model's specific implementation risk vs. a broad SORT-
# category ground-truth risk), legitimate matches land in the 0.44-0.50 band
# that 0.50 clips off, while the highest true-negative (0.42) stays safely
# below 0.45 so specificity is not sacrificed. Revisit against a real run.
MATCH_THRESHOLD = 0.45


def risk_text(r: dict) -> str:
    """Same field concatenation as the TF-IDF prototype, for continuity."""
    return f"{r.get('description', '')} {r.get('mitigation') or ''}".strip()


_model_cache: dict[str, "object"] = {}


def _get_model(model_name: str):
    """Lazy-load and cache the sentence-transformer model.

    Deferred import: sentence-transformers (and its torch dependency) is slow
    to import and unnecessary for callers that only want risk_text() or the
    pure-Python matching logic (e.g. unit tests with pre-computed embeddings).
    """
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer

        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def _cosine_matrix(gen_vecs, gt_vecs):
    """Cosine similarity matrix between two lists of embedding vectors."""
    import numpy as np

    a = np.asarray(gen_vecs)
    b = np.asarray(gt_vecs)
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
    return a_norm @ b_norm.T


def match_project(
    generated: dict,
    ground_truth: dict,
    model_name: str = EMBEDDING_MODEL,
    threshold: float = MATCH_THRESHOLD,
) -> dict:
    """Match one project's generated risk register against its ground truth.

    Mirrors scratch/match_metrics_prototype.py's matching algorithm exactly
    (greedy, highest-similarity-first, one-to-one) so that a future
    side-by-side comparison of TF-IDF vs. embedding matching is an
    apples-to-apples check of the similarity function only, not a change in
    matching strategy too.
    """
    gen_risks = generated.get("risks", [])
    gt_risks = ground_truth.get("risks", [])

    if not gen_risks or not gt_risks:
        return {
            "project_id": ground_truth.get("project_id"),
            "embedding_model": model_name,
            "threshold": threshold,
            "matches": [],
            "gen_risks": gen_risks,
            "gt_risks": gt_risks,
        }

    model = _get_model(model_name)
    gen_texts = [risk_text(r) for r in gen_risks]
    gt_texts = [risk_text(r) for r in gt_risks]
    gen_vecs = model.encode(gen_texts, convert_to_numpy=True, show_progress_bar=False)
    gt_vecs = model.encode(gt_texts, convert_to_numpy=True, show_progress_bar=False)

    sim = _cosine_matrix(gen_vecs, gt_vecs)

    pairs = []
    for gi in range(len(gen_risks)):
        for ti in range(len(gt_risks)):
            pairs.append((float(sim[gi, ti]), gi, ti))
    pairs.sort(reverse=True, key=lambda x: x[0])

    matched_gen, matched_gt = set(), set()
    matches = []
    for score, gi, ti in pairs:
        if score < threshold:
            break
        if gi in matched_gen or ti in matched_gt:
            continue
        matched_gen.add(gi)
        matched_gt.add(ti)
        matches.append(
            {
                "gen_risk_id": gen_risks[gi]["risk_id"],
                "gt_risk_id": gt_risks[ti]["risk_id"],
                "similarity": round(score, 3),
                "gen_category": gen_risks[gi]["category"],
                "gt_category": gt_risks[ti]["category"],
                "category_agree": gen_risks[gi]["category"] == gt_risks[ti]["category"],
            }
        )

    return {
        "project_id": ground_truth.get("project_id"),
        "embedding_model": model_name,
        "threshold": threshold,
        "matches": matches,
        "gen_risks": gen_risks,
        "gt_risks": gt_risks,
    }


_RAW_OUTPUT_NAME_RE = re.compile(
    r"^(?P<project_id>.+?)__(?P<model>.+?)__(?P<prompt>.+?)__run(?P<run>\d+)\.json$"
)


def parse_raw_output_filename(path: Path) -> Optional[dict]:
    """Parse the results/raw_outputs/ naming convention (see run_experiments.py):

        <project_id>__<model>__<prompt_strategy>__run<N>.json

    Returns None if the filename doesn't match - callers should fall back to
    the file's own JSON content (project_id/model/prompt_strategy/run_index
    fields) rather than trust the filename alone, but the filename is parsed
    too as a sanity cross-check.
    """
    m = _RAW_OUTPUT_NAME_RE.match(path.name)
    if not m:
        return None
    d = m.groupdict()
    d["run"] = int(d["run"])
    return d


def score_raw_output(raw_output_path: Path, threshold: float = MATCH_THRESHOLD) -> dict:
    """Score a single raw_outputs/ file against its project's ground truth.

    Handles the case where generation itself failed to produce parseable JSON
    (run_experiments.py stores raw_response_text + parsed_risks=null in that
    case) by returning a result with matches=[] and a parse_failed flag,
    rather than crashing - a model that cannot follow the output schema at all
    is itself a real (if blunt) data point for RQ2, not something to hide by
    erroring out of the scoring run.
    """
    with open(raw_output_path, encoding="utf-8") as f:
        run_record = json.load(f)

    project_id = run_record.get("project_id")
    parsed = run_record.get("parsed_risks")

    gt_path = GROUND_TRUTH_DIR / f"{project_id}.json"
    if not gt_path.exists():
        raise FileNotFoundError(
            f"No ground truth for project_id={project_id!r} "
            f"(looked in {gt_path}) - cannot score {raw_output_path.name}"
        )
    with open(gt_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    result = {
        "run_file": raw_output_path.name,
        "project_id": project_id,
        "model": run_record.get("model"),
        "prompt_strategy": run_record.get("prompt_strategy"),
        "run_index": run_record.get("run_index"),
        "parse_failed": parsed is None,
    }

    if parsed is None:
        result.update(
            {
                "embedding_model": None,
                "threshold": threshold,
                "matches": [],
                "gen_risks": [],
                "gt_risks": ground_truth.get("risks", []),
            }
        )
        return result

    match_result = match_project(parsed, ground_truth, threshold=threshold)
    result.update(match_result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", help="Score every file in results/raw_outputs/"
    )
    parser.add_argument("--file", type=str, help="Score a single raw_outputs/ file")
    parser.add_argument(
        "--threshold",
        type=float,
        default=MATCH_THRESHOLD,
        help=f"Similarity threshold for a match (default {MATCH_THRESHOLD} - see module docstring)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(SCORED_DIR),
        help="Directory to write per-run match tables (default results/scored/)",
    )
    args = parser.parse_args()

    if not args.all and not args.file:
        parser.error("Specify --all or --file <path>")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        targets = [Path(args.file)]
    else:
        targets = sorted(RAW_OUTPUTS_DIR.glob("*.json"))
        targets = [t for t in targets if t.name != ".gitkeep"]

    if not targets:
        print(f"No raw output files found in {RAW_OUTPUTS_DIR}", file=sys.stderr)
        sys.exit(1)

    for raw_path in targets:
        result = score_raw_output(raw_path, threshold=args.threshold)
        out_name = raw_path.stem + ".match.json"
        out_path = out_dir / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        n_matches = len(result["matches"])
        n_gt = len(result["gt_risks"])
        n_gen = len(result["gen_risks"])
        flag = " [PARSE FAILED]" if result.get("parse_failed") else ""
        print(f"[match] {raw_path.name} -> {n_matches} matched (gen={n_gen}, gt={n_gt}){flag}")
        print(f"  -> wrote {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
