# Pre-flight report: full-grid run readiness

> **STALE as of 2026-07-23 - the dollar figures below no longer apply.**
> This report was written for the original paid model triple (Anthropic
> Claude / OpenAI GPT / Together AI Llama), which was replaced after all
> three provider accounts hit real billing/quota errors on the first spend
> attempt - see `PROJECT_SPEC.md`'s RQ2 correction note and
> `docs/model_tier_recommendation.md`'s dated addendum. The current lineup
> (Gemini + 2 SambaNova-served open-weight models, all free-tier - moved off
> Groq the same day after its free tier proved unable to serve this
> project's real prompt sizes) has an
> estimated real cost of **$0.00**, not the $21-63 figures below - the
> entire cost-guard conflict this report exists to document no longer
> applies to a real run. Left in place, not deleted: the grid-composition
> checks (Section 1) and the `--batch` mechanics this report validated are
> still real, accurate history for how that decision was reached, and the
> batch code itself is still intact (see `run_experiments.py`'s module
> docstring) in case a future funded run reverts to paid accounts.

Run 2026-07-21, before any API spend. Everything below was executed against the
real repo with the provider calls either stubbed or not reached (`--estimate-only`).
**No API calls were made, no `.env` was created or modified, nothing was written
to `results/raw_outputs/`.**

Purpose: the first execution of the 567-call, ~$60 grid should not be the first
execution of the code that drives it. This checks the guards, the grid
composition, and the money; and surfaces one genuine conflict that needs a
decision before August.

---

## 1. Grid composition: CORRECT

`python src/run_experiments.py --estimate-only` reports **189 grid cells**
(21 projects × 3 models × 3 prompts), matching the frozen design.

Verified specifically that `all_project_ids()` reads `corpus_manifest.csv` and
filters on `inclusion_status == "included"` rather than globbing
`data/processed/`. This matters: `data/processed/` holds **22** `.txt` files
because `extract.py` also processes the set-aside outlier
`P-REGION-AIM4Learning`. A directory glob would have silently pulled it back
into the grid (22 × 9 = 198 cells) and into the paper. The code already guards
this and says so in its docstring; no defect, but now pinned by a test
(`TestGridComposition`).

Cross-checked the corpus while I was in there: **21 included projects, all 21
have both `data/ground_truth/*.json` and `data/processed/*.txt`.** The 3
manifest rows with no artifacts are correctly `set_aside` (AIM4Learning) or
`excluded` (Sizewell C, Connect To Work), each with a written reason. Clean.

## 2. Cost guard: WORKS, and it will stop the run you actually want

The guard behaves exactly as designed:

```
COST GUARD: estimated $63.16 exceeds the $30 threshold (PROJECT_SPEC.md).
Re-run with --confirm-cost to proceed, after checking the estimate above is sane.
```

exit code **1**, and `results/raw_outputs/` still had **0 files** afterwards;
it stops *before* spending, not partway through.

**But that is the headline finding, not a footnote.** Measured against the
decided configuration (`claude-sonnet-5` / `gpt-5.6-terra` /
`meta-llama/Llama-3.3-70B-Instruct-Turbo` @ $1.04/$1.04, as pre-filled in
`.env.example`):

| Runs per cell | API calls | Estimated cost | vs. $30 guard |
|---|---|---|---|
| 1 | 189 | **$21.05** | under |
| 2 | 378 | **$42.11** | **over** |
| 3 | 567 | **$63.16** | **over** |

Per-model, per run: claude $7.76 · gpt $10.34 · opensource $2.96.

**PROJECT_SPEC.md asks for two things that cannot both hold at current pricing:**
"2-3 runs each" (Methodology rules) and "STOP for confirmation if projected cost
> $30" (Coding standards). The guard is doing its job; the plan is what needs a
decision. This is a research-design call, so it is flagged here rather than
resolved:

- **Run once ($21.05)**: fits the guard, but loses the run-to-run variance the
  2-3 run design exists to measure. Weakens the paper.
- **Use `--confirm-cost` and accept ~$42 (2 runs) or ~$63 (3 runs)**: the guard
  is explicitly designed to be overridden after a human looks at the estimate.
  This is probably the intended path; the guard is a speed bump, not a ceiling.
- **Batch APIs.** Anthropic and OpenAI both offer 50%-off batch processing.
  Batching claude+gpt only (leaving the open-source slot at list price) gives
  ~$12.01/run → **~$24.02 for 2 runs, under the guard**, and ~$36.03 for 3 runs.
  Costs latency (batch jobs are asynchronous), which is fine for a grid that
  isn't interactive. *Not verified: whether Together AI offers a batch discount
  for the open-source slot; the figures above conservatively assume it does not.*

## 3. Two numbers that need reconciling before anyone budgets from them

**(a) `docs/model_tier_recommendation.md` is now stale for the decided config.**
The memo's Mid-triple table says $19.44/run and $38.89 at 2 runs; the measured
estimate for what was actually decided is **$21.05/run and $42.11 at 2 runs**.
The gap is the open-source slot: the memo priced the Mid triple with *DeepSeek
Pro* (~$1.34/run implied), but the slot was subsequently decided as *Llama 3.3
70B Turbo* at $1.04/$1.04 (~$2.96/run). The memo's batch figure ($31.19 for 2
runs) also doesn't reconcile with my computed $24.02; possibly a different
batch assumption. **I did not edit the memo**; whichever set of numbers gets
quoted in the paper should be recomputed once, from the config actually used.

**(b) The Sonnet 5 introductory rate expires 2026-08-31.** Already documented in
the memo (post-intro: $3/$15, i.e. claude rises from $7.76 to $11.63 per run).
Restating it here only because of the collision with the timeline: PROJECT_SPEC.md's
deadline for "corpus + pipeline + full experiment run" is **end of August 2026**.
That is zero margin. If the grid slips into September, 2 runs goes from $42.11
to roughly $49.85. Worth running before the deadline for pricing reasons, not
just scheduling ones.

## 4. Output-token assumption: conservative, but not by as much as it looks

`estimate_cost` assumes the worst case (`max_output_tokens` = 4096) for every
call. Measured against the 21 real ground-truth registers:

- risks per register: min 1, median 4.0, mean 4.1, max 8
- serialized size: median ~4,255 chars ≈ **1,064 tokens**; max ~8,640 ≈ 2,160

So a *human-sized* register is ~4× under the assumption. **But do not assume the
estimate is therefore 4× too high**; models are expected to over-generate
(that expectation is why `SHORT_REGISTER_SUBGROUP` exists), and at ~300
tokens/risk a 12-risk generated register lands near 3,600 tokens, close to the
cap. Treat $42/$63 as realistic, not padded.

## 5. `.env` does not exist: this is the actual blocker

`python src/check_env.py` reports all three providers `not configured`; there is
no `.env` file yet. Sampling, blinding, extraction, matching, metrics, and
figures all run without it, but **no model call can happen until `.env` is
created from `.env.example` and the three keys are filled in.** Per PROJECT_SPEC.md
that is a keys-handling step, so it is left entirely to Madhu; I did not create
the file.

## 6. New tests covering all of the above

`tests/test_run_pipeline.py` (19 tests, all passing, no network/keys/spend;
provider calls stubbed):

- **Reproducibility contract:** `run_one` writes `model_version`, `run_date`,
  `temperature`, `prompt_sha256` into both the raw record and
  `results/run_config.jsonl`, exactly as PROJECT_SPEC.md requires.
- **Append-only:** re-running the same `run_index` raises `FileExistsError`;
  `next_free_run_index` accumulates 1→2→3 and tracks each cell independently.
- **Filename round-trip:** `run_experiments.raw_output_path` →
  `match.parse_raw_output_filename`; the two conventions can no longer drift
  apart silently.
- **Leakage guard:** trips on a poisoned few-shot template naming a real corpus
  project; and, more directly, the *rendered prompt* for a real project is
  asserted not to contain any ground-truth risk description.
- **Failure handling:** a model returning prose is recorded as a parse failure
  with the raw text preserved, not raised; a refused temperature is recorded as
  `temperature_applied: false` rather than silently logged as applied.
- **Cost estimator:** scales linearly with runs; an unpriced model is reported in
  `models_missing_pricing_data` rather than silently costed at $0 (the dangerous
  failure; a $0 estimate that reads as "free").

## Verdict

The pipeline is mechanically ready. Guards work, the grid is the right shape,
the corpus is complete and consistent, and the code paths that will run 567
times have now been executed at least once each under test.

Two things are genuinely blocked on a human: **`.env` + keys**, and **the
2-3-runs vs. $30-guard conflict** in section 2. Neither is an engineering
problem.
