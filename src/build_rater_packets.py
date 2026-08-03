"""build_rater_packets.py - sampling, blinding, and packet assembly for Method B.

Implements docs/rater_protocol.md sections 3.1 (sampling) and 3.2 (blinding),
which that document explicitly flagged as "Not yet built." Method B is the
expert-Likert-rating arm of the study (PROJECT_SPEC.md); this script decides WHICH
generated registers get rated, assigns each an opaque code, records the
(gitignored) code->truth mapping, and lays out a per-rater randomized order.

What it produces (all reproducible from --seed):
  - results/rater_packets/blinding_map.csv   [GITIGNORED - the de-anonymizing
    key: code -> project_id, model, prompt_strategy, run_index]. Never share
    with raters. .gitignore has a rule for this path.
  - results/rater_packets/rater_assignments/<rater_id>.csv  [shareable: opaque
    codes only, in that rater's independently-shuffled order, with blank score
    columns - the scoring spreadsheet docs/rater_protocol.md section 5 describes].
  - results/rater_packets/packets/<code>.md  [shareable rater packet: the
    project's planning text + the generated register rendered as a readable
    table, under its opaque code only. Produced only for sampled registers
    whose generation output already exists in results/raw_outputs/; the rest
    are listed as "pending generation" - see the STATUS note below].
  - results/rater_packets/sampling_summary.json  [reproducibility record: seed,
    parameters, per-cell composition, counts].

STATUS / what can run now vs. later:
  - Sampling + blinding + per-rater assignment need only the ENUMERABLE grid
    (included projects x models x prompts) and run fully NOW, before any model
    is called. This mirrors how src/check_env.py was built and tested ready
    ahead of API keys existing.
  - The PACKET RENDERING step needs results/raw_outputs/ populated (real
    generated registers). Until then it renders packets for whatever exists
    (e.g. a pilot) and reports the rest as pending, rather than failing.

LEAKAGE: packets contain ONLY data/processed/<project>.txt (the same planning
text models saw) plus the generated register. This script never reads
data/ground_truth/ or data/risk_source_audit/ - raters must not see the human
"answer key" (docs/rater_protocol.md section 1). The blinding map (which reveals
model/prompt) is the one sensitive output and is gitignored.

DESIGN QUESTIONS RESOLVED 2026-07-20/21 (docs/rater_protocol.md section 3.1 now
says "21 included" throughout, not "18" - this docstring previously repeated
that stale project count and misstated the --min-uk-per-cell default below;
both are corrected here rather than left to compound):
  - --sample-per-cell (default 5, per the doc's proposal) x 9 cells = 45
    registers. The doc's original "45" assumed 18 projects; the number of
    DISTINCT projects drawn now depends on the current 21-project pool, but
    5-per-cell is preserved as the proposal.
  - --min-uk-per-cell **default is 1**, DECIDED 2026-07-20 by Madhu (was 0 -
    the naive random draw - before that decision). A naive draw could miss all
    3 UK documents across all 9 cells; 1 guarantees >=1 UK register per
    (model x prompt) cell (>=9 UK registers total, empirically 11 at the
    default seed - see docs/rater_protocol.md section 3.1). Pass 0 to restore
    the naive unstratified draw.
  - --exclude-short-register drops the metrics.py SHORT_REGISTER_SUBGROUP
    (thin registers reported separately for Method A) from the eligible pool.
    Default OFF (Method B rates register QUALITY independently of register
    size); exposed because whether those belong in the human-rated sample is
    also a project-owner call.

Usage:
  python src/build_rater_packets.py                 # default sample, 4 raters
  python src/build_rater_packets.py --min-uk-per-cell 1 --raters 3
  python src/build_rater_packets.py --seed 20260720 --sample-per-cell 5
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiments import MODEL_DISPATCH, PROMPT_FILES, raw_output_path  # single source of truth for the grid + naming
from metrics import SHORT_REGISTER_SUBGROUP

REPO_ROOT = Path(__file__).resolve().parent.parent


def _show(path: Path) -> str:
    """Repo-relative display where possible, else the absolute path (an
    --out-dir outside the repo is legal and must not crash the final print)."""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(Path(path).resolve())


MANIFEST_PATH = REPO_ROOT / "data" / "corpus_manifest.csv"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUT_DIR = REPO_ROOT / "results" / "rater_packets"

MODELS = list(MODEL_DISPATCH)      # ['claude', 'gpt', 'opensource']
PROMPTS = list(PROMPT_FILES)       # ['zero_shot', 'few_shot', 'structured']

DEFAULT_SEED = 20260720
DEFAULT_SAMPLE_PER_CELL = 5        # docs/rater_protocol.md section 3.1 proposal
DEFAULT_RATERS = 4                 # docs/rater_protocol.md section 6 (middle of the 3-5 range)


def included_projects() -> list[str]:
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        return sorted(
            row["project_id"]
            for row in csv.DictReader(f)
            if row["inclusion_status"] == "included"
        )


def is_uk(project_id: str) -> bool:
    return project_id.startswith("P-UK-")


def sample_cells(
    projects: list[str],
    per_cell: int,
    min_uk_per_cell: int,
    seed: int,
) -> list[dict]:
    """For each (model, prompt) cell, sample `per_cell` DISTINCT projects
    without replacement, optionally forcing at least `min_uk_per_cell` UK
    projects into each cell. Cells are sampled independently (a project may
    recur across cells), per docs/rater_protocol.md section 3.1.

    Determinism: a single seeded RNG is advanced cell by cell in a fixed
    (model, prompt) order, so the same seed reproduces the same sample exactly.
    """
    rng = random.Random(seed)
    uk = [p for p in projects if is_uk(p)]
    non_uk = [p for p in projects if not is_uk(p)]

    if per_cell > len(projects):
        raise ValueError(f"--sample-per-cell {per_cell} exceeds eligible pool size {len(projects)}")
    if min_uk_per_cell > len(uk):
        raise ValueError(
            f"--min-uk-per-cell {min_uk_per_cell} exceeds the {len(uk)} UK projects in the pool"
        )
    if min_uk_per_cell > per_cell:
        raise ValueError("--min-uk-per-cell cannot exceed --sample-per-cell")

    registers = []
    for model in MODELS:
        for prompt in PROMPTS:
            chosen: list[str] = []
            if min_uk_per_cell:
                chosen.extend(rng.sample(uk, min_uk_per_cell))
            remaining_pool = [p for p in projects if p not in chosen]
            chosen.extend(rng.sample(remaining_pool, per_cell - len(chosen)))
            chosen.sort()
            for pid in chosen:
                registers.append({
                    "project_id": pid,
                    "model": model,
                    "prompt_strategy": prompt,
                    "cell": f"{model}/{prompt}",
                })
    return registers


def assign_codes(registers: list[dict], seed: int) -> list[dict]:
    """Assign opaque REG-### codes. The code order is itself shuffled (seeded)
    so a code's number leaks nothing about its cell/model/prompt."""
    rng = random.Random(seed + 1)
    shuffled = registers[:]
    rng.shuffle(shuffled)
    for i, reg in enumerate(shuffled, start=1):
        reg["code"] = f"REG-{i:03d}"
    # restore a stable, human-readable order for the (gitignored) map file
    shuffled.sort(key=lambda r: r["code"])
    return shuffled


def per_rater_orders(codes: list[str], n_raters: int, seed: int) -> dict[str, list[str]]:
    """Independent per-rater shuffle of the packet order (section 3.2), each
    derived deterministically from the base seed so the layout is reproducible."""
    orders = {}
    for r in range(1, n_raters + 1):
        rng = random.Random(seed + 100 + r)
        order = codes[:]
        rng.shuffle(order)
        orders[f"rater{r}"] = order
    return orders


def render_register_table(parsed: dict) -> str:
    """Render a generated register as a readable markdown table (section 1) -
    never the raw JSON. Columns per prompts/output_schema.json."""
    risks = parsed.get("risks", []) if parsed else []
    lines = ["| # | Description | Category | Likelihood | Impact | Mitigation |",
             "|---|---|---|---|---|---|"]
    for i, r in enumerate(risks, start=1):
        desc = str(r.get("description", "")).replace("|", "\\|").replace("\n", " ")
        cat = str(r.get("category", ""))
        lk = r.get("likelihood", "")
        im = r.get("impact", "")
        mit = str(r.get("mitigation") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {i} | {desc} | {cat} | {lk} | {im} | {mit} |")
    if not risks:
        lines.append("| - | (register is empty or generation produced no parseable risks) | | | | |")
    return "\n".join(lines)


def render_packet(reg: dict) -> tuple[str | None, str]:
    """Return (packet_markdown_or_None, status). None + status if the generated
    register does not exist yet."""
    raw_path = raw_output_path(reg["project_id"], reg["model"], reg["prompt_strategy"], reg.get("run_index", 1))
    if not raw_path.exists():
        return None, "pending_generation"

    run_record = json.loads(raw_path.read_text(encoding="utf-8"))
    parsed = run_record.get("parsed_risks")
    if parsed is None:
        # A parse failure is a legitimate register-quality data point; still
        # render a packet noting the generation produced no valid register.
        table = "| - | (the generation did not produce a schema-valid register) | | | | |"
    else:
        table = render_register_table(parsed)

    planning_path = PROCESSED_DIR / f"{reg['project_id']}.txt"
    planning = planning_path.read_text(encoding="utf-8") if planning_path.exists() else "(planning text not found)"

    md = []
    md.append(f"# Review packet {reg['code']}")
    md.append("")
    md.append("You are reviewing the risk register in Part 2, using the planning documentation in "
              "Part 1. You are NOT told who or what produced the register - please do not try to "
              "guess. Score it on the three dimensions in your scoring sheet (Completeness, "
              "Accuracy/Plausibility, Actionability of Mitigations) and add any notable-issues note.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Part 1 - Project planning documentation")
    md.append("")
    md.append(planning.strip())
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Part 2 - Risk register to review")
    md.append("")
    md.append(render_register_table(parsed) if parsed is not None else table)
    md.append("")
    return "\n".join(md), "rendered"


def write_outputs(registers, orders, summary, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rater_assignments").mkdir(exist_ok=True)
    (out_dir / "packets").mkdir(exist_ok=True)

    # 1. Blinding map (GITIGNORED) - code -> truth.
    map_path = out_dir / "blinding_map.csv"
    with open(map_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "project_id", "model", "prompt_strategy", "run_index", "cell"])
        for r in registers:
            w.writerow([r["code"], r["project_id"], r["model"], r["prompt_strategy"],
                        r.get("run_index", 1), r["cell"]])

    # 2. Per-rater assignment sheets (shareable - codes only, blank scores).
    for rater_id, order in orders.items():
        with open(out_dir / "rater_assignments" / f"{rater_id}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["packet_code", "completeness_1to5", "accuracy_1to5",
                        "actionability_1to5", "notable_issues"])
            for code in order:
                w.writerow([code, "", "", "", ""])

    # 3. Packets (shareable) - only for registers whose generation exists.
    rendered = 0
    pending = 0
    for r in registers:
        md, status = render_packet(r)
        if status == "rendered":
            (out_dir / "packets" / f"{r['code']}.md").write_text(md, encoding="utf-8")
            rendered += 1
        else:
            pending += 1

    # 4. Reproducibility summary.
    summary["packets_rendered"] = rendered
    summary["packets_pending_generation"] = pending
    (out_dir / "sampling_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {"map_path": map_path, "rendered": rendered, "pending": pending}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"RNG seed (default {DEFAULT_SEED}), recorded in the summary")
    parser.add_argument("--sample-per-cell", type=int, default=DEFAULT_SAMPLE_PER_CELL,
                        help=f"Projects sampled per (model x prompt) cell (default {DEFAULT_SAMPLE_PER_CELL}, per rater_protocol section 3.1)")
    parser.add_argument("--min-uk-per-cell", type=int, default=1,
                        help="Force at least this many UK projects into each cell (default 1, DECIDED 2026-07-20 by Madhu - see docs/rater_protocol.md section 3.1; pass 0 for the naive unstratified draw)")
    parser.add_argument("--exclude-short-register", action="store_true",
                        help="Drop the metrics.py SHORT_REGISTER_SUBGROUP from the eligible pool (default: keep them)")
    parser.add_argument("--run-index", type=int, default=1, help="Which run to rate (default 1, per rater_protocol section 3.1)")
    parser.add_argument("--raters", type=int, default=DEFAULT_RATERS, help=f"Number of raters to lay out assignment sheets for (default {DEFAULT_RATERS})")
    parser.add_argument("--out-dir", type=str, default=str(OUT_DIR))
    args = parser.parse_args()

    pool = included_projects()
    if args.exclude_short_register:
        pool = [p for p in pool if p not in SHORT_REGISTER_SUBGROUP]

    uk_in_pool = [p for p in pool if is_uk(p)]
    print(f"[packets] eligible pool: {len(pool)} projects ({len(uk_in_pool)} UK); "
          f"grid = {len(MODELS)} models x {len(PROMPTS)} prompts = {len(MODELS)*len(PROMPTS)} cells")

    registers = sample_cells(pool, args.sample_per_cell, args.min_uk_per_cell, args.seed)
    for r in registers:
        r["run_index"] = args.run_index
    registers = assign_codes(registers, args.seed)

    distinct_projects = sorted({r["project_id"] for r in registers})
    uk_registers = [r for r in registers if is_uk(r["project_id"])]
    orders = per_rater_orders([r["code"] for r in registers], args.raters, args.seed)

    summary = {
        "seed": args.seed,
        "sample_per_cell": args.sample_per_cell,
        "min_uk_per_cell": args.min_uk_per_cell,
        "exclude_short_register": args.exclude_short_register,
        "run_index": args.run_index,
        "n_raters": args.raters,
        "models": MODELS,
        "prompts": PROMPTS,
        "eligible_pool_size": len(pool),
        "eligible_uk_projects": uk_in_pool,
        "n_registers_sampled": len(registers),
        "n_distinct_projects_in_sample": len(distinct_projects),
        "n_uk_registers_in_sample": len(uk_registers),
        "distinct_projects_in_sample": distinct_projects,
        "per_cell": {
            f"{m}/{p}": sorted(r["project_id"] for r in registers if r["cell"] == f"{m}/{p}")
            for m in MODELS for p in PROMPTS
        },
    }

    res = write_outputs(registers, orders, summary, Path(args.out_dir))

    print(f"[packets] sampled {len(registers)} registers across {len(distinct_projects)} distinct projects; "
          f"{len(uk_registers)} UK registers")
    print(f"[packets] blinding map (GITIGNORED): {_show(res['map_path'])}")
    print(f"[packets] rater assignment sheets: {args.raters}  |  packets rendered now: {res['rendered']}, pending generation: {res['pending']}")
    print(f"[packets] summary: {_show(Path(args.out_dir) / 'sampling_summary.json')}")
    if res["rendered"] == 0:
        print("[packets] NOTE: 0 packets rendered - results/raw_outputs/ has no generated registers "
              "for the sampled cells yet. Sampling/blinding/assignment are complete and reproducible; "
              "re-run after the experiment grid exists to populate packet bodies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
