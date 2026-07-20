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

## New task (highest priority): systematic leakage / page-range audit

Every excision bug this project has found - the SORT-table under-excision,
the Uganda over-excision, HyNet's 2-page draft offset - was caught by manually
opening a source document and checking page-by-page, never by trusting a
recorded range. That's only ever been done ad hoc, one document at a time,
sometimes by whichever of us happened to be looking at that file that day.
There's no systematic, rerunnable check that all 21 included projects are
actually leak-free and correctly excised right now - just a track record of
manual spot-checks that happened to catch 3 real bugs. Given how much of this
paper's validity rests on "the ground truth register never entered a model's
prompt," that gap is worth closing properly.

Build a script - suggest `src/audit_corpus.py` - that, for every row in
`corpus_manifest.csv` with `inclusion_status=included` (21 right now), does
two independent checks:

**1. Page-range re-verification (PDF-sourced projects only - 20 of 21).**
`P-UK-FreeBreakfastClubs` is the one exception: it's an HTML gov.uk
publication with no PDF and no page numbers at all (see its manifest row and
`data/ground_truth/P-UK-FreeBreakfastClubs.json` - `register_location` names
an HTML heading, not a page range). Skip page-verification for it; handle it
under check 2 instead (re-fetch its HTML and confirm the risk-bullet text is
still where `data/processed/P-UK-FreeBreakfastClubs.txt` and the ground truth
file expect).

For the other 20 (18 WB PDFs + `P-UK-HyNetCCUSCluster` +
`P-UK-PadeswoodCCUS`), open the real PDF in `data/raw/<project_id>/` with
PyMuPDF and independently re-derive where the risk-bearing section(s)
actually start and end, by searching page by page for the section heading
text itself (e.g. "KEY RISKS", "SORT", or for the UK docs the specific
numbered headings like "2.5 Identify high level potential risks") - the same
method used to catch all 3 bugs so far. Compare what you find against what
`corpus_manifest.csv`'s `sort_pages` / `section_v_pages` /
`proposed_excision_pages` columns claim. Note: WB rows and UK rows use these
columns slightly differently - WB uses `sort_pages` for the SORT table and
`section_v_pages` for the Key Risks narrative; UK rows have no SORT table
(`sort_present=N`) and repurpose `section_v_pages` to mean "the one section
used as the scored ground-truth register," with everything else listed in
`other_risk_mentions`. Read a couple of example rows of each type before
assuming one convention applies to both.

**2. Leak check (all 21, regardless of source type).** For each project, load
`data/ground_truth/<project_id>.json`, pull every risk's `description` and
`mitigation` text plus any distinctive IDs mentioned in it (e.g. HyNet's
"T1SR1"), and confirm none of it appears - verbatim or as an obvious
paraphrase-with-shared-fragment - in `data/processed/<project_id>.txt`. Also
check that `other_risk_mentions` content (sections that were excised for
leakage safety but aren't themselves scored - e.g. HyNet's Sections 1.6, 3.7,
4.2.4, 5.7) is genuinely absent from the processed text too, not just the
scored section.

**Output:** a clear per-project PASS / WARN / FAIL, printed and also written
to a report file (e.g. `results/corpus_audit_report.md` or similar - your
call). WARN for anything ambiguous (e.g. a heading found on a slightly
different page than claimed but the actual risk content still reads
correctly), FAIL for a confirmed leak or a genuinely wrong page range.

**Important - report only, don't auto-fix.** If the script finds a real
discrepancy, do NOT silently correct the manifest or ground truth file the way
we did for Uganda/HyNet - those corrections each needed a specific, written
explanation of what was wrong and why (see either row's `notes` for the
pattern). Flag findings clearly with the specifics (expected vs. actual page,
or the exact leaked substring and where it appeared) and let me or Madhu
decide the fix from there. The goal of this task is a trustworthy detector,
not an autonomous fixer - those are different levels of trust and shouldn't
be bundled into one script.

If everything comes back PASS, that's a genuinely useful result too - it
means the corpus is verified at a level stronger than "we happened to check
this one and it was fine."

## Ground rules (same as always, from CLAUDE.md)

- Never commit `data/raw/` or `.env`.
- Don't touch the frozen RQs or the leakage rule.
- The audit script is a new, separate file - it shouldn't need to modify
  `extract.py`/`match.py`/`metrics.py`/`run_experiments.py`/`judge.py`. If
  building it reveals you actually need to change one of those, stop and flag
  it rather than editing quietly - those are stable now and I'd want to know
  why.
- Separately, and not blocking your work at all: there's a large backlog of
  real, tested work (yours included) that has never been committed to git -
  everything's sitting as uncommitted/untracked changes. I'm handling that
  from the Cowork side; not something you need to do anything about.
- If you finish the audit and want more, ask before expanding scope further.
