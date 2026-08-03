# Figures pipeline (Task C) - build & validation report

**Status: pipeline built and exercised end to end against SYNTHETIC data.**
No real experiment has run (no API keys), so **every figure produced in this
task is illustrative / pipeline-validation only, not a real result.** Each PNG
carries a baked-in red "SYNTHETIC" caption to that effect. Regenerate all three
from real `metrics.py` output before any of them goes near the paper.

## What was built (new files only - no edits to metrics.py/match.py/corpus)

- `analysis/make_figures.py` - renders the three RQ figures from the JSON that
  `src/metrics.py --out <path>` writes. Committed, reusable against real data.
- `analysis/gen_synthetic_scored.py` - fabricates `*.match.json` fixtures in the
  exact schema `match.py.score_raw_output()` writes, so the real
  match.py -> metrics.py -> figures chain can be exercised now. Writes to the
  gitignored `scratch/synthetic_scored/`.
- `analysis/figures/fig_rq1_recall_precision.png`,
  `fig_rq2_model_prompt.png`, `fig_rq3_missed_hallucinated.png` - the three
  figures (synthetic input; see caveat above).

## The real code path was exercised (not hand-faked)

The point of the task was to test the pipeline, not to draw a picture. So:

1. `analysis/gen_synthetic_scored.py` wrote **36** synthetic `*.match.json`
   files: 2 projects x 3 models x 3 prompts x 2 runs.
2. The **real** `src/metrics.py` ran against them (unmodified):
   `python src/metrics.py --scored-dir scratch/synthetic_scored --out scratch/synthetic_metrics.json`.
   This is also the first time `metrics.py` has been run on more than the single
   Sao Tome pilot - i.e. the first real multi-model/multi-prompt exercise of
   `compute_all()`. It ran clean and produced sane aggregates (`n_scored_runs_total=36`,
   `n_parse_failed_total=2`).
3. `analysis/make_figures.py` ran against that real metrics output and all three
   figures rendered without error and were visually inspected (not just
   exit-code checked).

## The synthetic scenario (and why it was built that way)

Designed to make the figures non-degenerate and to hit every branch the real
data will hit:

- **Two real project_ids**, so downstream subgroup logic actually engages:
  - `P-KHM-BasicEducationImprovement` - a `SHORT_REGISTER_SUBGROUP` member
    (metrics.py): 1 ground-truth risk, models over-generate -> structurally low
    precision. This is the RQ3 over-generation test; it must be reported
    separately and never pooled into `corpus_wide`.
  - `P-SRB-CompetitivenessJobs` - an ordinary project: 6 ground-truth risks
    across several categories, **including one `category="other"` risk**.
- **A skill gradient** so RQ2 is legible: claude > gpt > opensource, and
  structured > few_shot > zero_shot. Weaker cells match fewer ground-truth
  risks and hallucinate more.
- **Deliberate variety**: real misses, real hallucinations, some matches with
  category disagreement, and a **parse-failure run** (the weakest cell,
  opensource/zero_shot on the short project) so the `parse_failed` path is
  covered (`n_parse_failed_total=2`, one per run).
- The `category="other"` case is included specifically to prove the RQ3 figure
  handles it correctly (see below).

All fabricated numbers live in gitignored `scratch/` (`scratch/synthetic_scored/`
+ `scratch/synthetic_metrics.json`), clearly labeled, so a synthetic number can
never be mistaken for a real one.

## What the three figures show (on this synthetic input)

**RQ1 - `fig_rq1_recall_precision.png`.** Grouped bars, two clearly separated
groups: *Corpus-wide (ordinary docs)* vs *Short-register subgroup (thin docs)*,
each with mean recall and mean precision, values annotated. On the synthetic
data the subgroup's precision (0.26) sits far below corpus-wide precision
(0.73) while its recall is comparable - exactly the over-generation signature
the separate reporting exists to expose. The title states the two groups are
never pooled.

**RQ2 - `fig_rq2_model_prompt.png`.** Two annotated 3x3 heatmaps (mean recall in
blues, mean precision in oranges), model on the y-axis, prompt on the x-axis,
each cell annotated with its exact value (white text on dark cells, black on
light). **Chose a heatmap over an 18-bar grouped chart** because the RQ2
question is explicitly "how do results vary across models *and* prompts" - a
2-D interaction a heatmap shows at a glance while the annotations preserve exact
numbers. On the synthetic data the recall heatmap darkens cleanly toward
claude/structured (1.00) and lightens toward opensource/zero_shot (0.25).

**RQ3 - `fig_rq3_missed_hallucinated.png`.** Diverging horizontal bars, one per
category: missed count to the left (red), hallucinated count to the right
(blue), counts annotated, axis padded so no label is clipped. **The `"other"`
category is handled correctly and legibly**: generated risks can never be
`category="other"` (forbidden by `prompts/output_schema.json`'s enum - see
`match.py`'s docstring), so `"other"` structurally always has
`hallucinated_count=0`. The figure marks it `other *` and carries a footnote
explaining this is expected, not missing data - so an all-red bar there does not
read as a gap.

## Caveats and hand-off notes

- **These PNGs are synthetic.** They sit in `analysis/figures/` (the location
  PROJECT_SPEC.md reserves for the paper's real figures) because the task specified
  that output path and asked for them to be rendered and inspected there - but
  they are disposable. Overwrite them by re-running the two commands below once
  real `results/scored/*.match.json` exists; the SYNTHETIC caption disappears
  automatically when `--note` is omitted (or set to a real-run label).
- `make_figures.py` is corpus/data-agnostic: it reads any `metrics.py --out`
  JSON. For the real run:
  ```
  python src/match.py --all                 # once results/raw_outputs/ is populated
  python src/metrics.py --scored-dir results/scored --out results/scored_metrics.json
  python analysis/make_figures.py --metrics results/scored_metrics.json
  ```
- No real corpus, ground-truth, `metrics.py`, or `match.py` file was modified.
  `results/scored/` real output directory is untouched (still just `.gitkeep`).
