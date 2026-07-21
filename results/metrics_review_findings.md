# metrics.py review — two analysis-scoping findings (report-only)

**RESOLVED 2026-07-21 (Madhu, via AskUserQuestion).** Finding 1: both
recommendations adopted — the asymmetry is documented in the paper draft
(Section III.F) AND `compute_all()` now also reports
`by_model_and_prompt_corpus_wide_only` / `by_category_corpus_wide_only`
alongside the unchanged full-corpus defaults. Finding 2: "report both ways" —
`by_category` is unchanged (still includes parse failures, as originally
found) and a new `by_category_excluding_parse_failures` sits alongside it.
Independently re-verified against a real code re-read (not just this memo's
own prose) and a live dry run before implementing — Finding 2 in particular
was independently reproduced via a from-scratch mocked pipeline run before
this memo was even read in full. Both variants are now covered by
`tests/test_metrics.py::TestComputeAllScopeAndParseFailureVariants` (51/51
suite passes). See `src/metrics.py`'s module docstring and `compute_all()`
for the implementation. Original findings below, left intact for the record.

---

Found during a pre-run correctness pass on `src/metrics.py` (the code that turns
`*.match.json` into the paper's RQ1/RQ2/RQ3 numbers), 2026-07-21. **Report-only,
following this repo's established `corpus_audit_review_notes.md` pattern — no
code was changed [at the time this was written — see RESOLVED note above].**
Both are *methodology-scoping* questions, not arithmetic bugs: the code does
exactly what it says, but "what it says" has a consequence for how the
paper's numbers should be read, and resolving it is Madhu/Kruthik's call
(it's an analysis-design decision, not an engineering default). Both were
verified concretely against `scratch/synthetic_metrics.json`.

---

## Finding 1 — RQ1 and RQ2/RQ3 are computed over *different* document sets

`compute_all()` builds `corpus_wide` by **excluding** the 5-document
`SHORT_REGISTER_SUBGROUP` (correct and documented — thin registers must not be
pooled into the headline RQ1 recall/precision). But `by_model_and_prompt` (RQ2)
and `by_category` (RQ3) are computed over **`per_run`, i.e. all documents
including the subgroup.**

Verified on the synthetic data:
- `corpus_wide` n_runs = **18** (ordinary docs only)
- `by_model_and_prompt` total n_runs = **36** (includes the KHM subgroup runs)

**Why it matters:** a reader comparing the RQ1 headline precision to an RQ2
per-cell precision is comparing numbers over different document sets. The
subgroup exists precisely because its precision is structurally low
(over-generation against a 1-2 risk register), so including it in the RQ2 cells
drags every model's per-cell precision down in a way the RQ1 headline
deliberately avoids.

**Possibly intended** — one can argue RQ2 ("how does each model×prompt cell
behave") legitimately wants *all* documents. The `metrics.py` docstring only
promises the subgroup is never pooled into the "headline corpus-wide" number,
and is silent on RQ2/RQ3. So this may be a deliberate choice that just needs to
be **stated explicitly in the paper's methodology** ("RQ2/RQ3 aggregates include
the short-register subgroup; RQ1 headline excludes it"). If instead RQ2 should
match RQ1's document set, `aggregate_by_model_prompt` / `aggregate_by_category`
would need to take the subgroup-excluded list (or report both with/without).

**Recommendation:** confirm intended, then either (a) document the asymmetry in
the paper, or (b) add subgroup-excluded variants of the RQ2/RQ3 aggregates so all
three headline numbers cover the same corpus. No change made pending that call.

---

## Finding 2 — parse-failures inflate RQ3's per-category "missed" counts

`aggregate_by_category()` counts, per run, every ground-truth category with no
matching generated risk as "missed." For a `parse_failed=True` run,
`gen_risks=[]`, so **every** ground-truth category of that project is counted as
missed — a JSON-format failure is scored identically to a genuine
category blind-spot.

Verified on the synthetic data: `n_parse_failed_total = 2` (the KHM
opensource/zero_shot runs), and `environmental` `missed_count` = **4**, of which
2 come from those parse-failure runs where *nothing at all* was generated.

**Why it matters:** RQ3 is the paper's core contribution — "which risk categories
do LLMs systematically miss or hallucinate." If a weak model frequently fails to
emit valid JSON, RQ3 will attribute those failures to whatever categories the
affected projects happen to contain, conflating "can't produce parseable output"
with "has a blind spot for category X." That muddies exactly the signal RQ3 is
meant to isolate.

**Recommendation (stronger of the two):** for `by_category`, consider excluding
`parse_failed` runs (they're already surfaced via `n_parse_failed_total` and per
cell in `by_model_and_prompt`), or report category-miss counts twice — including
and excluding parse failures — so a model's genuine category coverage is
separable from its output-format reliability. This is a small, localized change
to `aggregate_by_category` if the researchers want it, but it changes RQ3's
numbers, so it's flagged, not applied.

---

## Not findings (checked, fine)

- `run_metrics` recall/precision/category-accuracy division-by-zero guards are
  correct (all use `if <denominator> else None`, and `_safe_mean` drops `None`).
- `match.py` greedy one-to-one matching is deterministic (stable sort; ties
  broken by original index order) and correctly stops at the threshold.
- The `category="other"` artifact (generated risks can never be "other", so it
  always shows hallucinated_count=0) is already correctly documented in
  `match.py` and made legible in the RQ3 figure — not a defect.

Neither finding blocks the run; both are about how to *report* the results once
real numbers exist, and both are cheap to address in `metrics.py` if the
researchers decide to. Left unapplied because they change the meaning of the
paper's numbers.
