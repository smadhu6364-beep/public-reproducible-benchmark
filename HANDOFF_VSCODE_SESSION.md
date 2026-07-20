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
  verified working/solid on this end - thank you. Tasks A, B, C, and D are
  all done (see below) - Task E (rater recruitment channel research) is
  next.
- Bugs found and fixed so far, for context on why the new task exists: a
  systemic SORT-table under-excision (8 WB documents), a Uganda over-excision
  (9 legitimate pages wrongly cut), and HyNet's page-offset (found by you).
  Three real bugs, each only caught by directly re-opening the source and
  checking page-by-page rather than trusting a recorded range. That pattern is
  the whole motivation for the task below.

## What's genuinely still blocking a full experiment run

Progress since the last handoff on both, but neither is actually resolved yet:

1. **Model tier: DECIDED, keys: still missing.** Madhu picked the "Mid"
   triple (`docs/model_tier_recommendation.md`) - Sonnet 5 intro + GPT-5.6
   Terra + a cheap open model. `.env.example` now has the confirmed, exact
   API model ID strings pre-filled for Claude (`claude-sonnet-5`) and GPT
   (`gpt-5.6-terra` - note the bare `gpt-5.6` alias currently routes to Sol,
   not Terra). Two things remain: (a) `.env` itself still has no real API
   keys - that's Madhu's account/billing action, not engineering; (b) the
   open-source slot needs a specific hosted-provider pick (Together AI /
   Fireworks / Groq / DeepInfra) before its exact model-ID string can be
   set, since the string format differs by provider even for the same
   model (DeepSeek V4 Pro) - this part *could* be a small task if asked for,
   but isn't queued right now. `check_env.py` is still ready and tested for
   the moment real keys land.
1a. **NEW 2026-07-21: `call_gpt()` fixed for a GPT-5.6-Terra compatibility
    risk found by code review + web search, not yet real-call-verified.**
    Sourced evidence (checked 2026-07-20/21) says OpenAI's GPT-5 reasoning
    family rejects the legacy `max_tokens` chat-completions parameter (now
    `max_completion_tokens`) and may reject `temperature` outright in
    reasoning mode - directly relevant since Terra is the just-decided GPT
    slot, and CLAUDE.md requires temperature 0-0.2 uniformly across all 3
    models. `call_gpt()` in `src/run_experiments.py` now sends
    `max_completion_tokens` unconditionally and defensively retries without
    `temperature` if the API specifically rejects it - logging a loud stderr
    warning and recording `temperature_applied: false` on the raw output
    record and `run_config.jsonl` line rather than silently pretending
    uniformity held. Verified with a mocked `openai.OpenAI` client (3
    scenarios: normal success, temperature-rejected retry, an unrelated 400
    correctly propagating uncaught) - all pass - but **this is still
    unverified against a real API call**, since no `OPENAI_API_KEY` has
    existed at any point. If you're the one who ends up making the first
    real GPT call: check `results/run_config.jsonl`'s `temperature_applied`
    field on those first runs before trusting anything downstream of them.
    `call_opensource()` was deliberately left untouched (still classic
    `max_tokens`) - third-party OpenAI-compatible endpoints serving open-
    weight models aren't evidenced to share this constraint, and changing
    it without evidence risked breaking a path that currently works. Also
    added a paragraph to the paper draft's Limitations section (V.A)
    disclosing this as a real, possible deviation from "temperature
    controlled across all 3 models" if it fires for real. Not committed to
    `data/` or `.env` - only `src/run_experiments.py`, `.env.example`, this
    file, and the paper draft.
2. **Rater recruitment: materials drafted, channels being researched, zero
   raters actually contacted yet.** `docs/rater_recruitment_outreach.md` has
   a ready-to-send invitation and qualifying criteria. Task E (below) is
   researching realistic channels. Neither of these is recruitment itself -
   that step still needs Madhu/Kruthik reaching a real person, and status
   there is unchanged: unknown, and the actual bottleneck.

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

## Tasks A and B - done, thank you (verified independently before committing)

**Task A (matching threshold validation) - fully done.** Real
`all-MiniLM-L6-v2`, 17 unambiguous hand-labeled pairs (WB + UK + cross-
project hard cases) plus 4 borderline cases reported separately, run through
the actual match.py cosine pipeline at a threshold sweep. Clean separation
(should-match 0.52-0.81, should-not-match 0.20-0.42). `MATCH_THRESHOLD`
lowered 0.5 -> 0.45 with a specific, defensible rationale (margin above the
lowest true positive; recovers legitimate granularity-mismatch matches 0.50
was clipping) - now live in `src/match.py`, well-documented. Nothing further
needed here unless a real experiment run later suggests revisiting it.

**Task B (rater-packet sampling/blinding) - infrastructure done; packet
rendering blocked on real generations, not on you.** Sampling, blinding, and
per-rater assignment sheets all work and are reproducible from a seed.
Verified deterministic, and the leakage guard holds (packets never read
`data/ground_truth/`). The UK-representation question you correctly left
open (rather than silently picking) is now DECIDED: `--min-uk-per-cell 1`
(I re-ran `build_rater_packets.py` with it and changed the script's own
default so a future re-run doesn't silently revert to the fragile naive
draw - see `docs/rater_protocol.md` §3.1 for the reasoning and the live
sample's composition, now 11 UK registers across the 45 with every one of
the 9 cells covered). Packet *content* rendering is genuinely still at 0/45
- that needs `results/raw_outputs/` populated by a real run, which needs
API keys. Nothing more to do on Task B until then.

## Task C - done, thank you (verified independently before committing)

`analysis/make_figures.py` + `analysis/gen_synthetic_scored.py` are both
committed. Exercised the real chain end to end: 36 synthetic match.json
fixtures -> real (unmodified) `metrics.py` (first time it's run on more than
the single pilot - ran clean, `n_scored_runs_total=36`) -> real
`make_figures.py` -> 3 PNGs in `analysis/figures/`. I opened and looked at
all three, not just checked for a zero exit code - RQ1's two-group split,
RQ2's heatmap, and RQ3's correctly-handled `"other"` category all look right
and publication-reasonable. Every figure carries the baked-in red SYNTHETIC
caption, and `results/figures_pipeline_report.md` is thorough and gives the
exact re-run commands for real data. No real corpus/ground-truth/metrics.py/
match.py file touched. Nothing further needed here until real experiment
data exists to regenerate the figures against.

## Task D - done, thank you (independently verified before committing)

`docs/model_tier_recommendation.md` is committed. I checked it carefully
before trusting it, not just on your word: re-derived the token-count
arithmetic by hand and spot-checked ~10 of the memo's dollar figures across
both the per-model and batch-discount tables (all matched exactly),
cross-checked the Claude slot against this session's own knowledge of the
current lineup (correct), and independently web-searched the GPT-5.6
pricing rather than trusting the memo's own citations - Sol/Terra/Luna
pricing and the GA date both confirmed exactly. Real, trustworthy research,
not just a plausible-looking table. `.env` and `run_experiments.py` are
both untouched, as instructed - the model choice is still Madhu's.

I also did one thing myself in parallel while this ran: `src/judge.py`
(Method C) had never been tested at all, unlike match.py (Task A). Built no
new permanent file for it (Method C is supplementary-only, lower stakes),
but ran `parse_judge_response()` against 8 hand-built adversarial responses
and `judge_one()` end-to-end with a fake injected judge-caller against the
real pilot generation. Found and fixed one real bug: Python's `bool` is a
subclass of `int`, so `{"completeness": true, ...}` was silently accepted
as a score of 1. Fixed in `src/judge.py`, committed, re-verified clean.

### Task E: research realistic channels for finding Method B raters

Rater recruitment (CLAUDE.md's Method B: 3-5 practitioner raters) is a real,
currently-unaddressed bottleneck - not corpus work, not pipeline code, and
not something either of us can do directly (neither Claude session can
actually contact and recruit a human). What we *can* do is the research
legwork, the same pattern as Task D: I drafted the actual outreach message
and qualifying criteria (`docs/rater_recruitment_outreach.md` - read it
first for the exact profile needed: real PM experience on complex/
infrastructure/public-sector-scale projects, comfortable with risk
registers as a working artifact, not an ML background). Your environment
has real internet access this sandbox doesn't - use it to find where such
people might actually be reached, not just to speculate.

Write `docs/rater_recruitment_channels.md` covering:
- **Free/organic channels:** specific, real professional associations (PMI,
  APM, or sector-specific equivalents for infrastructure/international-
  development work) and whether they have an actual mechanism for this kind
  of ask (a member forum, a research-participation board, local chapter
  contacts) rather than just a general website. Same for relevant LinkedIn
  groups or university PM-programme alumni/faculty pages - name real ones
  if you can find them, don't just describe the category.
- **Paid channels (in case Madhu decides "paid" on the outreach doc's open
  question):** expert-network or user-research platforms that could supply
  a handful of qualified PM professionals for a few hours each (e.g.
  Respondent.io, User Interviews, or similar) - with approximate cost per
  participant if published, since that interacts with CLAUDE.md's cost
  awareness even though the $30 guard is specifically about API spend, not
  this.
- **Realistic timeline:** given each channel, how long from "post/ask" to
  "have 3-5 confirmed raters" - this is the actual thing that matters
  against the Aug-2026 deadline, more than which channel is theoretically
  best.

This is research and reporting only - do not draft new outreach copy
(`rater_recruitment_outreach.md` already covers that) and do not contact
anyone or sign up for anything.

**Task E: done, thank you (independently re-verified before committing).**
`docs/rater_recruitment_channels.md` is solid - well-scoped (stayed research/
reporting only, no outreach sent, no signups), correctly prioritized warm/
targeted asks over broadcast for an n=3-5 recruit, and cited. Spot-checked 3
load-bearing figures via independent web search rather than trusting them:
APM's membership count and Respondent.io's incentive ceiling for senior/
in-person raters were both slightly off (APM understated the corporate
count; Respondent's incentive range was capped too low for senior/executive
in-person screens, which also revised the paid-platform budget estimate
upward for that scenario) - corrected inline, doesn't change the recommended
sequence.

**One thing to flag, not just silently accept:** you also wrote
`docs/opensource_slot_options.md` (exact provider/model-ID strings closing
the open-source slot gap from Task D) - useful, and it says the right things
about not touching `.env`/`run_experiments.py` and leaving the choice to
Madhu, but **Task E didn't ask for this and the ground rules say to ask
before expanding scope further, not after.** This time the content held up
fine (one real correction needed: the Groq model-ID table conflated two
separate deprecation announcements, fixed inline), so no harm done, but
please check back before adding a task's-worth of unrequested scope next
time, even when it's this useful - that's not a formality, it's how a
two-session project stays coordinated rather than each side quietly
expanding in parallel.

## Ground rules (same as always, from CLAUDE.md)

- Never commit `data/raw/` or `.env`.
- Don't touch the frozen RQs or the leakage rule.
- Task E is research/reporting only - a new doc file, no code changes, no
  outreach sent, no signups. If it reveals you need to touch something
  outside this scope, stop and flag it rather than editing quietly.
- The git backlog mentioned in earlier handoffs is resolved - everything's
  committed now, working tree was clean before this round of tasks started.
  I'm still committing your work from the Cowork side as it lands, same as
  before - nothing you need to do differently.
- Task E is pre-approved - no need to check back before starting it. If you
  finish it and want still more, ask before expanding scope further.
