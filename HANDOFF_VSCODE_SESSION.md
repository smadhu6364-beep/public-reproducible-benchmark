# Handoff for the VS Code / local Claude Code session

**Written 2026-07-19, directly into the repo this time** (the previous handoff file
from earlier today was written only to the Cowork session's temporary scratchpad,
not this repo, so it never actually reached this session - if you saw a reference
to a `handoff_for_vscode_session.md` that didn't exist, that's why. This file is
the real one, committed to disk where you can actually read it.)

## Where the project stands right now

- Corpus is done, full stop: **21 included projects** (18 World Bank PADs + 3
  UK business cases: HyNet CCUS FBC, Padeswood CCUS SBC, Free Breakfast Clubs
  SBC), 2 UK candidates explicitly excluded with documented reasoning
  (Sizewell C - no itemized register at all; Connect to Work - a real but
  degenerate 2-risk/zero-mitigation/zero-category-diversity register), 1 WB
  project set aside as a labeled outlier. All 21 included projects have
  schema-validated ground truth JSON in `data/ground_truth/` and leak-checked
  planning text in `data/processed/`. Thank you for Task 0 - the page
  corrections you found on HyNet (every recorded page was off by 2, plus two
  risk-bearing sections the draft never reached) were real, substantive
  catches, independently confirmed.
- `src/extract.py`, `src/match.py`, `src/metrics.py`, `src/run_experiments.py`,
  `src/judge.py` are all real, implemented, tested code. `src/check_env.py`
  (your Task 2) and `docs/rater_protocol.md` (your Task 1) are both done and
  verified working/solid on this end - thank you. No outstanding tasks from
  the previous handoff remain; see the new task below.
- Bugs found and fixed so far, for context on why the new task exists: a
  systemic SORT-table under-excision (8 WB documents), a Uganda over-excision
  (9 legitimate pages wrongly cut), and HyNet's page-offset (found by you).
  Three real bugs, each only caught by directly re-opening the source and
  checking page-by-page rather than trusting a recorded range. That pattern is
  the whole motivation for the task below.

## What's genuinely still blocking a full experiment run

Not corpus work, not pipeline code - two things outside either of our control,
unchanged since the last handoff:

1. `.env` has no API keys configured (Anthropic, OpenAI, and an undecided
   open-source model access path - HF hosted inference vs. a self-hosted
   OpenAI-compatible endpoint). This is Madhu's call, not something to fill in
   guessing at values. (Your `check_env.py` is ready and tested for the moment
   this changes - verified it runs clean with no `.env` present: reports all
   three providers "not configured", exits 0, no crash.)
2. Human expert rater recruitment for Method B (Likert ratings, Fleiss' kappa)
   - status unknown to either of us as far as I can tell from the repo. Your
   rater_protocol.md is solid and ready to hand to recruited raters whenever
   that happens - nothing there is blocking anything.

## Previous tasks (Task 0, Task 1, Task 2) - all done, thank you

UK PDF sourcing/verification, the rater protocol, and the env checker are all
complete and independently verified on this end. Full history is in git log /
`corpus_manifest.csv` notes if you want it; not repeating it here since it's
done, not actionable.

## Previous task (leakage/page-range audit) - done, thank you

17 PASS / 1 WARN / 3 FAIL, all hand-verified before reporting rather than
trusted raw - real work, and you caught 3 bugs in your own detection
heuristics along the way, which says good things about how carefully this
was done. Padeswood WARN and Morocco FAIL were both correctly identified as
false positives. Peru and Uganda FAILs were real leaks - I independently
re-verified both against the actual PDFs myself before fixing (found a
second leak on the same Peru page you didn't call out - R04's E&S finding,
restated right next to the R03 finding you flagged), then extended their
excision ranges, re-ran extract.py, and re-verified clean. All committed.
`src/audit_corpus.py` is now part of the permanent toolkit - it's a good
`--all` scan to re-run any time the corpus changes.

## Three tasks (do Task A, then Task B, then Task C - Task C is pre-approved, no need to check back before starting it)

### Task A: validate Method A's matching quality against real embeddings

`src/match.py`'s docstring says it plainly: `EMBEDDING_MODEL =
"all-MiniLM-L6-v2"` and `MATCH_THRESHOLD = 0.5` are "first-pass defaults, not
empirically validated against this corpus." Every test of `match_project()`
so far (including the one done to build match.py itself) used a mocked fake
encoder - deterministic bag-of-words hashing, not a real model - because this
sandbox can't reach huggingface.co to download one. That means the actual
semantic-matching quality that Method A's headline recall/precision numbers
will depend on has never been checked against anything real. Your
environment can download the real model; this sandbox can't.

What to do:
1. Install `sentence-transformers` if not already (it's in requirements.txt)
   and confirm you can actually load `all-MiniLM-L6-v2` - this alone is
   something to report if it fails, since it would mean the pipeline's
   default model choice needs to change regardless of threshold.
2. Build a small, hand-constructed test set - not real model output (none
   exists yet), but plausible stand-ins for it. Pick a mix of 3-4 ground
   truth registers, including at least one World Bank register (e.g.
   `P-SRB-CompetitivenessJobs`, has 6 real risks) and the UK
   `P-UK-HyNetCCUSCluster` register (different phrasing style/framing -
   worth checking the matcher works across both, not just WB-style text).
   For each real risk in those registers, write:
   - a "should-match" paraphrase - different wording, same underlying risk,
     roughly what a reasonably good model might plausibly generate
   - a "should-NOT-match" distractor - include some *hard* negatives (same
     category, genuinely different specific risk) alongside easy ones, since
     easy negatives won't stress-test the threshold meaningfully
3. Call `match_project()` directly (see `src/match.py` - it takes two dicts
   each shaped like `{"risks": [...]}`, exactly the ground truth JSON shape)
   with your constructed "generated" register against the real ground truth,
   using the real model. Do this at a few threshold values (e.g. 0.3, 0.4,
   0.5, 0.6, 0.7), not just the current default - report the trade-off, not
   a single pass/fail.
4. Report: does 0.5 actually separate your should-match cases from your
   should-NOT-match cases? If not, what threshold does, and by how much
   margin? If you have time, try one alternate embedding model (e.g.
   `all-mpnet-base-v2`) as a stretch check, but the threshold analysis on
   the current model is the actual priority.

**This is allowed to end in a recommendation, not just a report** - unlike
the audit task, changing `MATCH_THRESHOLD`'s default is a normal parameter-
tuning decision, not something touching leakage-sensitive corpus data. If the
evidence clearly favors a different threshold, go ahead and change the
default in `src/match.py` (update the docstring's "known limitations" note
to say it's now been checked against a hand-built test set, not just
asserted). If it's genuinely ambiguous, say so and leave the default alone
rather than picking one arbitrarily.

Write your test set and findings to something like
`results/matching_validation_report.md` so the hand-built pairs are
reviewable, not just a black-box verdict. Be explicit that this validates the
*matching mechanism* using constructed proxies, not real model output - a
further check once real generations exist is still worthwhile, this just
catches an obviously bad default before any real API budget gets spent on it.

### Task B: build Method B's packet-generation code

`docs/rater_protocol.md` §3.1-3.2 designed a specific sampling and blinding
scheme but says plainly the actual code was never written. Build it now so
it's ready to fire the moment raters are recruited, rather than starting a
build cycle after that.

One thing to fix while you're in there: §3.1 says "sample 5 of the 18
projects" - that's stale, the corpus is 21 now (the UK documents were added
after that doc was written). Update the doc's own numbers to 21, and decide
(your call, but state the reasoning) whether the 5-per-cell sample should be
drawn from all 21 or should guarantee UK representation given only 3 of the
21 are UK documents and one of those is the short-register-subgroup
Free Breakfast Clubs entry - it would be easy for a naive random draw to
never include a UK document at all across all 9 cells.

Build:
- The sampling script: for each of 9 model x prompt cells, sample 5 projects
  without replacement, seeded RNG (record the seed), same 45 registers for
  every rater (full overlap, per §3.1).
- The blinding mechanism: assign an opaque code (`REG-014` style) per sampled
  register, write the mapping to `results/scored/rater_blinding_map.csv`
  (must be gitignored - check `.gitignore` covers `results/scored/` contents
  appropriately, or add a specific rule for this file; it maps code ->
  project_id/model/prompt/run and must never be shown to raters).
- Per-rater packet order randomization (a different shuffle per rater, per
  §3.2).
- Since no real generations exist yet, test this against placeholder/
  synthetic register data (there's a real pilot generation already at
  `scratch/pilot_STP_zeroshot.json` if that's a useful fixture, or construct
  something synthetic - your call) so the logic is verified working, not
  just written.

Do NOT build the Fleiss' kappa computation script - `rater_protocol.md` §4
explicitly says that should wait until real ratings exist to test it
against, and that reasoning still holds. Packet generation and kappa
computation are different concerns; this task is only the former.

### Task C: build the analysis/figures/ pipeline (RQ1/RQ2/RQ3)

`src/metrics.py`'s `compute_all()` (exposed via `--out <path>`) already
computes every number the paper's Results section will need, structured for
exactly this: `corpus_wide` (RQ1 - overall recall/precision),
`by_model_and_prompt` (RQ2), `by_category` (RQ3 - missed vs. hallucinated
counts per category), and `short_register_subgroup` (the 5-document over-generation
test - see paper draft Section III.A/F, reported separately, never pooled
into `corpus_wide`). No figures exist yet, and metrics.py has never been run
against more than the single São Tomé pilot generation - this task is also
the first real exercise of the full match.py -> metrics.py chain against a
multi-model, multi-prompt dataset, since no real experiment has run yet.

What to build, in `analysis/make_figures.py` (writing PNG outputs to
`analysis/figures/` - both paths already reserved in CLAUDE.md's repo
structure; please don't add a 6th script to `src/` for this, CLAUDE.md says
to maintain that directory's file list exactly as the 5 named pipeline
scripts):

1. RQ1 figure: corpus-wide mean recall and mean precision (`corpus_wide`)
   shown alongside, never blended with, the short-register subgroup's mean
   precision/recall (`short_register_subgroup`) - two clearly labeled
   groups, not one pooled bar.
2. RQ2 figure: a 3x3 grouped bar chart or heatmap (your call - state which
   and why) of recall and precision from `by_model_and_prompt`, one
   cell/group per `"<model> / <prompt>"` key.
3. RQ3 figure: per-category missed vs. hallucinated counts from
   `by_category`, one diverging bar per category (missed one direction,
   hallucinated the other). Handle "other" correctly: generated risks can
   never have category="other" (forbidden by `output_schema.json`'s enum -
   see match.py's own docstring), so "other" will structurally always show
   hallucinated_count=0 - that's expected and correct, not a bug or a data
   gap, and the figure/caption should make that legible rather than let it
   look like missing data.

Since no real experiment output exists, test this against synthetic data,
the same way Task B's placeholder testing works:

4. Write a small synthetic-data generator producing match.json-shaped
   fixtures (the real schema match.py writes: project_id, model,
   prompt_strategy, run_index, embedding_model, threshold, matches,
   gen_risks, gt_risks) across a representative slice of the real grid - all
   3 models, all 3 prompts, and at least 2 projects, including one
   short-register-subgroup project (e.g. P-KHM-BasicEducationImprovement)
   and one ordinary project (e.g. P-SRB-CompetitivenessJobs) - with enough
   deliberate variation (some misses, some hallucinations, some category
   disagreement, at least one parse_failed=true run) that the figures
   aren't just plotting an empty or degenerate case.
5. Run the real `src/metrics.py --scored-dir <synthetic dir> --out <path>`
   against that synthetic data - do not hand-write a fake metrics.py output;
   the point is to exercise the real code path end to end (match.json ->
   metrics.py -> figures), since this doubles as the first test of
   metrics.py at more than one project/model/prompt at a time.
6. Run `analysis/make_figures.py` against that real output and confirm all
   3 figures render without error and look sane - open them and look,
   don't just check for a zero exit code.

Keep the synthetic fixtures in a clearly labeled, gitignored scratch
location (e.g. `scratch/synthetic_scored/`, same precedent as other scratch
work in this project) so a synthetic number is never mistaken for a real
one later. State plainly, in the script's docstring and in your report, that
every figure produced this way is illustrative/pipeline-validation only, not
a real result - the same caveat applied everywhere else pipeline code has
been tested ahead of real data.

Do not touch `src/metrics.py`, `src/match.py`, or any real corpus/ground-truth
file for this task - it's new file(s) only, same rule as Task B.

Write a short report to `results/figures_pipeline_report.md`: what you
built, the synthetic scenario you constructed and why, and a description of
what the 3 figures look like on that synthetic input.

## Ground rules (same as always, from CLAUDE.md)

- Never commit `data/raw/` or `.env`.
- Don't touch the frozen RQs or the leakage rule.
- Task A may edit `src/match.py` (that's the point, if the evidence supports
  a threshold/model change) but not `extract.py`/`metrics.py`/
  `run_experiments.py`/`judge.py`. Task B and Task C should be new, separate
  file(s) - Task C specifically goes in `analysis/`, not a 6th file in
  `src/` (see Task C for why). If any task reveals you need to touch
  something outside this scope, stop and flag it rather than editing
  quietly.
- The git backlog mentioned in earlier handoffs is resolved - everything's
  committed now, working tree was clean before this round of tasks started.
  I'm still committing your work from the Cowork side as it lands, same as
  before - nothing you need to do differently.
- Tasks A, B, and C are all pre-approved - no need to check back before
  starting any of them. If you finish all three and want still more, ask
  before expanding scope further.
