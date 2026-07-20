# Corpus Inclusion Criteria

**Updated 2026-07-20 to match what the project actually does now.** The
original version of this file (written before the pipeline existed) described
a planned checklist, a `candidate` status value, a `pages_excised` column, and
a purely-manual excision process. None of those match the real
`data/corpus_manifest.csv` schema or `src/extract.py`/`src/audit_corpus.py`
that now exist. This version describes the actual, applied methodology.

A candidate project is included only if it passes **all four gate checks**
below. Record the outcome in `data/corpus_manifest.csv`'s `inclusion_status`
column, which in practice takes one of three values: `included`, `excluded`
(fill `exclusion_reason`), or `set_aside` (a labeled outlier kept in the
manifest for transparency but not part of the scored corpus - fill
`exclusion_reason` the same way). There is no `candidate` status in practice;
a row is added to the manifest once real content has been checked, not
before.

## The four-point gate (all must pass)

1. **Rated risk content present.** A structured, rated risk table or
   equivalent exists - the World Bank SORT table for PADs, or the closest
   analog for a non-PAD document (Section 2 below covers what "closest
   analog" has meant in practice for UK documents).
2. **Substantive, itemized narrative risk section present.** Beyond a rated
   table, there must be an itemized narrative discussion of at least one
   real, specific risk (not a single generic sentence). A document with only
   a rated table and no narrative, or only a one-sentence narrative with no
   itemized content, fails this check (see the two documents rejected on
   exactly this basis in Section 3).
3. **A locatable, cleanly excisable boundary between planning and risk
   content.** The risk content's page range (or, for the one HTML-only
   document in the corpus, its section boundary) must be independently
   re-verifiable against the source document itself, not just against a
   previously recorded range - see "Leakage control" below for why this is
   checked twice, not once.
4. **>=15 pages of planning content survive excision.** After the risk
   content is cut, enough planning documentation must remain to plausibly
   reason about risks from. (The corpus's one HTML-only document has no page
   count to check this against; inclusion for that document rested on the
   other three checks plus a separate short-register-subgroup judgment call
   - see the paper draft, Section III.A.)

Partial fields in the extracted ground truth are acceptable if `description`
and `category` are present; note gaps in the ground-truth file's own `notes`
field rather than fabricating a value for a missing one - `likelihood`,
`impact`, and `sort_rating` are `null`-able in the ground-truth schema for
exactly this reason (see `data/ground_truth/*.json` for real examples of a
source giving no rating at all).

## Recording rules (matching the real corpus_manifest.csv columns)

- **`doc_urls`**: if a project has multiple planning documents, separate URLs
  with a pipe `|` inside the quoted CSV field. Only planning/appraisal docs go
  here - never `register_url`.
- **`register_url`**: the source of the human risk register (ground truth),
  kept separate from `doc_urls` so the leakage boundary is explicit in the
  manifest itself, not just in prose.
- **`publication_date`**: publication date of the planning document (YYYY-MM
  or YYYY-MM-DD; the document's own date, not a later approval date - these
  can differ, see `data/corpus_manifest.csv` notes for cases where they did).
  Needed for the contamination analysis below.
- **`sort_pages`** and **`section_v_pages`**: the page range(s) of the rated
  table and the narrative risk section, respectively. **These are the only
  two columns `src/extract.py` actually reads to decide what to excise** -
  it deliberately does not fall back to `other_risk_mentions` or
  `proposed_excision_pages` (below). Editing the wrong column silently
  produces under-excised planning text; this was a real bug caught and
  fixed during this project's own UK-sourcing work.
- **`other_risk_mentions`** and **`proposed_excision_pages`**: documentation/
  audit-only fields recording pages that look risk-adjacent but are not
  (yet) part of the actual excision range. Useful for a human reviewer, but
  have zero effect on what `extract.py` actually cuts - if a page needs to be
  excised, it must be added to `sort_pages`/`section_v_pages`, not just noted
  here.
- **`remaining_planning_pages`**: recomputed any time the excision range
  changes; used to check gate criterion 4 above.
- **`sector`**: short tag (e.g. transport, energy, health, water, education).
- **Provenance**: for every included project, save the raw PDF(s) locally
  under `data/raw/` (gitignored) and record the source URL in the manifest.

## Leakage control: code-enforced excision plus a standing audit tool

The original plan for this file was manual-only excision on the reasoning
that automated section-stripping would fail silently across document
formats. That reasoning held during initial corpus-building, but the
approach actually shipped is stricter than either "manual only" or "trust an
automated cut blindly":

1. **`src/extract.py` enforces excision at the code level.** It refuses to
   produce planning text for any project whose `sort_pages`/`section_v_pages`
   are not already recorded, rather than defaulting to "extract everything."
   Excised pages are written to a separate, clearly labeled audit location
   (`data/risk_source_audit/`), never the directory the prompting step reads.
2. **Every excision range is independently re-verified against the source
   document before ground truth is finalized on top of it** - not re-checked
   against the previously recorded range, checked against the document
   itself. This caught three distinct bug classes during corpus-building
   (narrative under-excision, SORT-table under-excision, and one
   over-excision) - see the paper draft, Section III.B, for the specifics.
3. **`src/audit_corpus.py` is a standing, re-runnable check**, not a one-time
   pass: for every included document it independently re-scans the source
   for heading/table patterns and separately greps the ground truth's own
   text against the processed planning text for verbatim or near-verbatim
   recurrence. Run any time the corpus changes. It has already caught two
   real leaks after the manual process above believed it was done (see the
   paper draft, Section III.B, and `results/corpus_audit_report.md`) - the
   tool has real false positives too (documented in the same places), which
   is exactly why it is a supplement to human review, not a replacement.
4. **The register itself never re-enters a prompt or a few-shot example**,
   including for a *different* project - see `prompts/few_shot.txt`, which
   uses a fully synthetic worked example for this reason.

This methodology is written up in full in the paper draft's Methodology
section (maintained separately per `CLAUDE.md` - `paper/` content is
Overleaf-linked, not stored in this repo).

## Pretraining contamination (public documents)

These are public documents; models may have seen some of them - risk content
included - during pretraining. Excision cannot fix that. Two mitigations,
both used:

- **The corpus deliberately spans both very recent and older documents**
  (see `publication_date` per row), rather than only trying to find
  post-cutoff documents - which would not have been achievable for a corpus
  this size without seriously distorting sector/region coverage.
- **A supplementary analysis compares performance on plausibly-seen vs.
  plausibly-unseen documents** using the recorded dates. A gap is itself a
  contamination signal worth reporting, not proof of contamination either
  way - see the paper draft's Limitations section for why this can only be
  suggestive, not dispositive.
- **Contamination is named as a limitation in the paper**, not something to
  discover only if a reviewer raises it.

## What the corpus actually is (as of this pass)

21 included projects: 18 World Bank Project Appraisal Documents (PADs) and 3
UK government business cases (Five Case Model format - HyNet CCUS, Padeswood
CCUS, Free Breakfast Clubs). The UK documents needed one methodology
addition beyond the gate above: a Five Case Model document scatters risk
content across several sections in incompatible framings rather than one
WB-style SORT table plus narrative, so ground truth for each UK document is
drawn from a single chosen section (the closest structural analog to a
WB register), while every other risk-bearing section is still excised for
leakage safety but never scored against. Full reasoning in the paper draft,
Section III.A.

2 UK candidates and 1 World Bank candidate were read in full and did not
clear the gate: one had no itemized or rated register anywhere in the
document (gate check 2), one had a real but degenerate two-risk register
with no mitigation content and no category diversity (gate check 2, a
weaker but still real failure), and one World Bank technical-assistance-only
grant's risk section did not itemize discrete risks per category (also gate
check 2) and was set aside as a labeled outlier rather than excluded
outright, since its risk content is real, just atypical.
