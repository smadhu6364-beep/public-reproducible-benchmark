# Method B Rater Protocol — Expert Likert Evaluation

**Status:** Draft proposal, written 2026-07-19. Everything below is a concrete
starting point for Madhu/Kruthik to accept, edit, or override — not a settled
decision. Sections marked **OPEN** are genuinely undecided and need a call
from the project owners, not an engineering default.

**Purpose:** CLAUDE.md specifies Method B as "expert Likert ratings + Fleiss'
kappa," alongside Method A (semantic matching vs. ground truth) and Method C
(LLM-as-judge, supplementary only). This document is the missing protocol for
Method B: what raters see, what they score, how registers are sampled and
assigned, and how kappa is computed from the results.

---

## 1. What raters see

For each register a rater is assigned, they receive a single self-contained
packet with two parts:

1. **The project's planning documentation** — the same text a model saw
   (`data/processed/<project_id>.txt`), or a trimmed excerpt of it if the
   full text is impractically long for a reviewer to read per item (see
   §6, packet length is an open sizing question).
2. **One generated risk register**, rendered as a readable table (risk
   description, category, likelihood, impact, mitigation) — never the raw
   JSON blob, since raters are project-management professionals, not ML
   engineers (see §5).

Raters do **not** see:
- Which model or prompting strategy produced the register (blinded — see §3).
- The project's human-authored ground-truth register
  (`data/ground_truth/<project_id>.json`) or any `risk_source_audit/`
  content, for the same leakage-adjacent reasoning that keeps it out of model
  prompts: seeing the "answer key" would contaminate an independent judgment,
  here of the human rater rather than the model.
- Other raters' scores, until every rater has independently submitted (§3).

This mirrors the ASCE 2025 construction-risk paper's critique of prior
ChatGPT-risk studies for non-anonymous evaluation bias (see
`docs/lit_review_foundation.md`, Theme 2, entry on blind peer review) — our
blinding is a direct, citable response to that criticism.

---

## 2. The Likert scale

Each rater scores **each register** (not each individual risk line) on three
1–5 dimensions, plus one optional free-text field:

| Dimension | 1 (poor) | 3 (adequate) | 5 (excellent) |
|---|---|---|---|
| **Completeness** | Misses risks an experienced PM would immediately flag from the planning docs alone | Covers the obvious risks but misses some non-trivial ones | Covers essentially the full risk surface a careful human review would surface |
| **Accuracy / Plausibility** | Risks are vague, generic, or not actually supported by the planning documents | Risks are plausible and mostly well-reasoned, with some weak or boilerplate entries | Every risk is specific, well-reasoned, and clearly traceable to the planning documents |
| **Actionability of Mitigations** | Mitigations are generic boilerplate ("monitor closely," "engage stakeholders") disconnected from the specific risk | Mitigations are reasonable but somewhat generic | Mitigations are specific, feasible, and directly address the stated risk |
| **Notable issues (free text, optional)** | — | — | — |

The free-text field exists specifically to feed RQ3 (failure-mode analysis)
— ask raters to note anything that reads as fabricated/hallucinated, wrongly
categorized, or duplicated, even briefly. This is qualitative signal
`match.py`'s automated semantic matching can't produce on its own.

Rating a register, not each risk line, keeps rater burden bounded regardless
of how many risks a given register contains — a 3-risk and an 11-risk
register both cost one scoring pass.

**Note for the paper's methodology section:** raters are told explicitly to
judge Completeness against what *they, as a PM professional, would expect
from the planning documents alone* — not against the (unseen) human register.
This is what makes Method B an independent check on Method A rather than a
redundant one: Method A measures overlap with one specific human register;
Method B measures whether the register is *good*, which is a different
question when the human register itself is imperfect or incomplete.

---

## 3. Blinding, sampling, and assignment

### 3.1 Sampling (OPEN — proposal below needs sign-off)

> **IMPLEMENTED 2026-07-20** in `src/build_rater_packets.py` (§3.1 sampling +
> §3.2 blinding). The script reads the *current* included-project pool from
> `corpus_manifest.csv` rather than a hard-coded number, so the stale "18"
> below is corrected in code automatically. The two genuinely-open design
> questions are exposed as flags, defaulting to the literal proposal here:
> `--min-uk-per-cell` (default 0 = the naive draw below; set 1 to guarantee UK
> representation — see the note after the bullets) and `--exclude-short-register`
> (default off). Kappa computation (§4) is now implemented too —
> `src/compute_kappa.py`, built 2026-07-22 (Task G1), see that section for
> details.

The full grid is 3 models × 3 prompts × **21** projects (the corpus grew from
18 to 21 included projects after this document was first drafted) =
**189 combinations**, each with 2–3 runs (CLAUDE.md). Rating all of it — well
over ~470 registers — is not realistic for 3–5 volunteer/practitioner raters.
**Proposal:**

- Rate only **run 1** of each combination for Method B. Multiple runs exist
  for Method A's statistical stability, not to give raters near-duplicate
  copies of the same cell to review.
- For each of the 9 (model × prompt) cells, randomly sample **5 of the 21
  projects** without replacement (seed the RNG and record the seed for
  reproducibility) → **45 registers total** for the whole rated set. (The 45
  is 5 × 9 cells and is unchanged by the pool growing from 18 to 21; only the
  per-cell draw is now from 21.)
- This guarantees every model and every prompt strategy has equal
  representation (RQ2), at a fixed, describable sample size, without
  requiring every project to appear in every cell.
- All recruited raters rate the **same 45 registers** (full overlap), not
  disjoint subsets. This keeps the Fleiss' kappa computation simple (§4) —
  a partial/balanced-incomplete-block design would let more registers get
  *some* coverage, but complicates kappa and isn't obviously worth it at
  this sample size. Flag for reconsideration if 45 × (3 items) turns out to
  be too much rater time (see §6 time-budget note).

**UK representation — DECIDED 2026-07-20 (Madhu): `--min-uk-per-cell 1`.**
With only 3 UK projects in a 21-project pool, a naive random draw can badly
under-sample or miss them — empirically, sweeping seeds through
`build_rater_packets.py` produced anywhere from 1 to 8 UK registers out of 45,
i.e. some seeds leave UK almost unrepresented across all 9 cells. Since the UK
documents are the study's only non-World-Bank, non-SORT documents and exist
specifically to test cross-template generalization (Section III.A of the
paper draft), leaving their representation in the human-rated sample to
chance would undercut that argument. The live sample (seed 20260720,
recorded in `results/rater_packets/sampling_summary.json`) now has 11 UK
registers across the 45, with every one of the 9 model×prompt cells
containing at least one.

**This 45-register number and the "run 1 only, full overlap" design are the
part of this document most likely to need Madhu/Kruthik revision** — they
trade off statistical power against real rater hours, which is a judgment
call, not something to lock in silently.

### 3.2 Blinding mechanism

> **IMPLEMENTED 2026-07-20** in `src/build_rater_packets.py`. Concretely: the
> mapping file is `results/rater_packets/blinding_map.csv` (**gitignored** — a
> `.gitignore` rule covers exactly this path; the shareable per-rater
> assignment sheets and packets alongside it carry codes only). Each per-rater
> packet order is an independent seeded shuffle. Everything is reproducible
> from `--seed`, which is recorded in `results/rater_packets/sampling_summary.json`.

- Each sampled register gets an opaque code (e.g. `REG-014`), assigned when
  rating packets are prepared.
- A separate mapping file (`results/rater_packets/blinding_map.csv` —
  **gitignored**, never shown to raters) records
  `code → (project_id, model, prompt_strategy, run_index)`. This mapping is
  only used after all ratings are in, to break out kappa/scores by model and
  prompt (RQ2) and to fold Method B into the paper's tables.
- Packet order is independently randomized per rater (a different shuffle
  per rater), to spread out any fatigue/order effects rather than having
  every rater see, say, the weakest model last.

### 3.3 Independence

Raters score independently and do not discuss registers with each other
until every rater has submitted all 45 scores. This is a precondition for
Fleiss' kappa to mean what it's supposed to mean (raters' agreement measured
against each other, not against a converged consensus).

---

## 4. Computing Fleiss' kappa

- Compute **separately per Likert dimension** (Completeness, Accuracy,
  Actionability) — three kappa values, not one pooled score, since they
  measure different things and could plausibly disagree in different ways
  (e.g. raters might agree strongly on Completeness but diverge on what
  counts as "actionable").
- Fleiss' kappa is defined over **nominal categories**; the standard
  approach (and the one this protocol uses) treats each of the 5 Likert
  points as a discrete category. This is a real simplification — a
  disagreement between 4-and-5 counts identically to a disagreement between
  1-and-5 — and should be stated as such in the paper's methodology
  section, citing Fleiss (1971) for the formula and Landis & Koch (1977) for
  the standard interpretation bands (<0 poor, 0.01–0.20 slight, 0.21–0.40
  fair, 0.41–0.60 moderate, 0.61–0.80 substantial, 0.81–1.00 almost
  perfect — see `docs/lit_review_foundation.md` Theme 5).
- **OPEN, optional:** if kappa on the raw 5-point scale comes out
  uninformatively low (a known risk with 5-category nominal kappa and a
  handful of raters), consider a documented fallback of collapsing to 3
  bands (1–2 / 3 / 4–5) and re-reporting, or citing an ordinal-aware
  agreement statistic alongside kappa. Don't decide this until real ratings
  exist — it's premature to pre-commit a fallback that might not be needed.
- Report kappa three ways, mirroring the subgroup structure `metrics.py`
  already uses for Method A: **overall** (all 45 registers), **by model**
  (15 registers per model), and **by prompt strategy** (15 registers per
  prompt) — this directly feeds RQ2 ("how do results vary across models and
  prompting strategies") with a human-judgment signal alongside Method A's
  automated one.
- Mean Likert scores (not just kappa) should also be reported per model and
  per prompt strategy — kappa tells you whether raters *agree*, the mean
  tells you what they agreed *about*. Both matter for RQ1/RQ2.
- **BUILT 2026-07-22 (Task G1):** `src/compute_kappa.py` implements exactly
  this — reads completed sheets from `results/rater_packets/rater_assignments/`
  plus `blinding_map.csv`, validates the full-overlap design above, and
  reports kappa (+ mean Likert scores) overall/by-model/by-prompt-strategy
  per dimension, plus collects `notable_issues` free text with model/prompt
  metadata for RQ3. Implemented directly with numpy rather than adding
  `scipy.stats`/`statsmodels` (neither is pinned in `requirements.txt`) —
  the formula is short and well-defined enough that a transparent direct
  implementation avoids a new dependency per CLAUDE.md's "ask before adding
  anything" rule. Verified against an independently hand-derived worked
  example in `tests/test_compute_kappa.py` (22 tests) — see that file
  before trusting a number out of this script on inspection alone. A
  synthetic demonstration (`analysis/gen_synthetic_kappa_demo.py`, fabricated
  scores, real code path, `scratch/synthetic_kappa_report.json`) shows the
  report's shape before real ratings exist, same pattern as
  `gen_synthetic_scored.py`/`gen_synthetic_cutoff_report.py`. Still and only
  blocked on real ratings actually existing — recruitment (section 6) is
  the bottleneck, not this code.

---

## 5. Rater instructions (for a PM professional, not an ML person)

Draft instructions to hand each rater, in plain language:

> You'll review a series of short packets. Each packet has two parts: (1) a
> project's planning/appraisal documentation, and (2) a risk register
> someone or something produced from it. You don't need any AI/ML
> background — read the planning documents the way you would for a real
> project, then judge the risk register the way you'd judge a colleague's
> risk register: does it cover what you'd expect, is it accurate and
> specific rather than generic, and are the proposed mitigations actually
> useful? You won't be told who or what produced each register, and that's
> intentional — please don't try to guess. Score each of the three
> questions from 1 to 5 using the descriptions provided, and add a note in
> the "notable issues" box if anything stands out as wrong, made-up, or
> duplicated — even a one-line note is useful. There's no time limit, but
> as a guide, budget roughly 5–8 minutes per packet.

**OPEN:** whether this is delivered as a spreadsheet (one row per register,
columns for the 3 scores + free text), a Google Form (one per register or
one long form), or something else is a tooling decision, not a protocol one
— left to whoever sets up rater logistics. A spreadsheet is the simplest
option that needs no new infrastructure and is recommended by default unless
Kruthik has a reason to prefer a form.

---

## 6. Time budget and recruitment (OPEN — not this document's call)

- 45 registers × ~5–8 min each ≈ **4–6 hours per rater** for the proposed
  sample size. If recruited raters are volunteering time rather than being
  compensated, this may be too much — worth confirming with actual
  candidates before finalizing §3.1's sample size, not after.
- CLAUDE.md specifies **3–5 raters**; this document assumes recruiting
  toward the middle of that range (4) but works unmodified at 3 or 5 — the
  sampling and kappa design in §3–4 don't depend on the exact count.
- **Rater recruitment status is unknown to me** (this session has no
  visibility into whether Kruthik has approached any practitioners). This
  is the actual bottleneck for Method B, not the protocol design — the
  point of this document is to make sure protocol design isn't *also*
  blocking recruitment once it starts.

---

## 7. Cross-references

- `CLAUDE.md` — Method B is specified here as "expert Likert ratings +
  Fleiss' kappa," and raters/reviewers must never see leakage-adjacent
  ground truth.
- `prompts/output_schema.json` — the generation schema being rendered into
  readable packets (§1).
- `src/metrics.py` — Method A's model/prompt/subgroup breakout pattern that
  §4's kappa reporting deliberately mirrors, so the paper's Method A and
  Method B tables read as one consistent analysis rather than two
  differently-shaped ones.
- `docs/lit_review_foundation.md` — Theme 4 (LLM-as-judge limitations,
  motivating why Method B/human judgment anchors Method C rather than the
  reverse) and Theme 5 (Fleiss/Landis & Koch citations).
