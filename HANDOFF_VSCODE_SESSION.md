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

1. **Model tier: fully DECIDED now, all three slots. Keys: still missing.**
   Madhu picked the "Mid" triple (`docs/model_tier_recommendation.md`) -
   Sonnet 5 intro + GPT-5.6 Terra + Llama 3.3 70B Turbo via Together AI (this
   last one decided 2026-07-21, closing the gap `docs/opensource_slot_options.md`
   researched). `.env.example` now has the confirmed, exact API model ID
   strings AND base URL/pricing pre-filled for all three - copy it to `.env`
   and add real keys, nothing else to decide. Only real API keys (all three
   providers) remain - that's Madhu's account/billing action, not
   engineering. `check_env.py` is still ready and tested for the moment they
   land. **Live-verified the full grid's cost estimate end-to-end** with all
   three slots configured (fake placeholder keys, `--estimate-only` never
   calls a real API): 189 cells, `models_missing_pricing_data` empty (all
   three price correctly now), **$42.11 for 2 runs** - over the $30 guard,
   so a real run will need `--confirm-cost` (consistent with Task D's
   memo's own ~$38.89 non-batch figure, small difference explained by Llama
   3.3 70B Turbo's exact pricing vs. the memo's original DeepSeek-Pro
   assumption for that slot). **Correction 2026-07-21:** this figure was
   first reported as $41.20 using `opensource_slot_options.md`'s original
   ~$0.88/MTok Together AI price; independently re-verifying that specific
   number directly against together.ai/pricing found the real current rate
   is $1.04/MTok (~18% higher, likely a stale figure in the original
   research) - `.env.example` and the memo are both corrected, and $42.11
   above is the re-run estimate with the right number. Small dollar amount,
   but flagging the correction itself: this is exactly why "independently
   verify, don't just relay" applies to my own numbers too, not only
   VS Code's. **UPDATE 2026-07-21 (later same day): the $30-guard-vs-"2-3
   runs" conflict this implied is now RESOLVED, not just flagged** - see the
   new dated section near the bottom of this file for `--batch`.
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

**NEW 2026-07-21: `tests/` and `results/metrics_review_findings.md` landed
next, again without checking back first.** Both are genuinely good work -
verified independently, not just trusted:
- `tests/` (49 tests across `test_extract.py`, `test_match.py`,
  `test_metrics.py`, `test_parsing.py`) - I read all four files and actually
  ran the suite (`python3 -m unittest discover -s tests`), including once
  against the real pinned `jsonschema==4.23.0` (the sandbox initially had an
  older version, which threw a deprecation warning that turned out to be a
  sandbox artifact, not a real issue). 49/49 passed. Good design choices:
  stubbing the embedding model and API calls (same pattern I independently
  used for my own end-to-end dry run, done in parallel, before I'd read this)
  so the suite needs no network/keys, and pinning the bool-as-int regression
  permanently. Genuinely useful, ongoing value.
- `results/metrics_review_findings.md` - a sharp, correct methodology review
  of `metrics.py` that caught something I'd missed myself despite reading
  that file multiple times this session: RQ1's headline excludes the
  short-register subgroup, but RQ2/RQ3 silently don't, and parse failures
  get counted as genuine category misses in RQ3. Both re-confirmed against
  the actual code (not just this memo's prose), and Finding 2 independently
  reproduced by my own from-scratch dry run before I'd even read the memo.
  Correctly scoped as report-only with no code changed pending a real
  decision - exactly right.

**But this is now the SECOND time in one session Task E turned into three
things.** First `docs/opensource_slot_options.md`, now a full test suite plus
a methodology review - both unrequested, both good, both landed without a
check-in. I resolved both open findings with Madhu directly (via
AskUserQuestion) and implemented the decisions in `metrics.py` +
`tests/test_metrics.py` myself, so nothing is blocked. But naming the pattern
plainly: two for two is a pattern, not a coincidence, and CLAUDE.md's "never
expand scope... without asking first" isn't scoped to just code - it covers
research and analysis too. Please actually stop and ask next time before
starting something Task E (or whatever the live task is) didn't ask for, even
when you're confident it's good - good unrequested work is still unrequested
work, and the point of asking isn't quality control, it's staying
coordinated on what each side is doing.

I also found and fixed one small real bug while re-verifying the test suite
against the actual figures pipeline (not part of your work - pre-existing in
`analysis/make_figures.py` from Task C): `main()`'s final print loop crashed
on a relative `--out-dir` (`p.relative_to(REPO_ROOT)` needs `p` resolved to
absolute first) - the figures still wrote correctly before the crash, so this
was cosmetic but real. Fixed with `.resolve()`, re-verified clean.

## NEW 2026-07-21 (later the same day): pre-flight report landed, batch API added, cost guard conflict resolved

Three more rounds of work since Task E, all verified independently before
committing, same standard as always:

**Landed `results/preflight_report.md`, `docs/run_playbook.md`,
`tests/test_run_pipeline.py`, `tests/test_rater_packets.py`.** Re-derived
every specific numeric claim myself rather than trusting the printed
output - grid size (189 cells), cost at 1/2/3 runs ($21.05/$42.11/$63.16),
per-model split, the corpus-manifest cross-check (22 processed files vs. 21
included, the extra one being the set-aside outlier) - all matched exactly.
Read both new test files in full (19 + a full blinding-integrity suite), ran
them for real. The preflight report's central finding is real and was worth
surfacing: CLAUDE.md asks for both "2-3 runs each" and "stop if cost exceeds
$30", and at the decided model triple's actual pricing those two requirements
cannot both hold (2 runs = $42.11, 3 runs = $63.16, both over $30). Good
catch - thank you.

**Took the guard-conflict finding to Madhu directly** (not picked silently):
answer was "2 runs, AND build batch-API support first" rather than overriding
the guard. So I implemented it: `src/run_experiments.py` now has `--batch`
(submits claude+gpt cells to Anthropic's and OpenAI's batch APIs at their
~50%-off rate, exits immediately without waiting) and `--batch-check`
(polls and collects, safe to re-run any number of times - batch jobs can take
up to 24h). opensource/Together AI is deliberately NOT batched - its
batch-discount availability was never verified, so it still runs
synchronously at list price in the same `--batch` invocation. Batched, 2 runs
comes to ~$24.02, clearing the guard with no override needed. Real SDK method/
field names (Anthropic `messages.batches.create/retrieve/results`; OpenAI
`files.create` -> `batches.create` -> `batches.retrieve` -> `files.content`)
were confirmed via `inspect.signature()` and direct source reads against the
actually-installed SDK versions, but **the submit/check cycle has never been
exercised against a live call** - no API key has ever existed for this
project. `tests/test_batch.py` (27 tests) verifies request/response shapes
against hand-built fakes matching those confirmed signatures and the full
submit-then-collect cycle, including failure rows, but a mock is still a
mock. If you're the one making the first real `--batch` call: read
`results/batch_jobs.json` and the first few batch-collected
`results/raw_outputs/*.json` records by hand before trusting anything
downstream - same discipline as the `call_gpt` temperature-retry path.

**Verified and landed 3 more test files** (`test_audit_corpus.py`,
`test_extract_excision.py`, `test_figures.py` - 203 tests total now). Found
one real thing worth knowing while re-running `audit_corpus.py` for real as
part of that verification: `P-UK-FreeBreakfastClubs`'s Check 1 is a live
re-fetch of the actual gov.uk publication (no PDF exists for it), and that
one check is environment-dependent - it got a `403 Forbidden` on the proxy
tunnel in this sandbox and reported WARN instead of PASS, while every other
project's page-range and leak-check status reproduced byte-for-byte
identically to what was already committed. Not a corpus problem, confirmed
by directly hitting the same URL with a bare `urllib` call and getting the
same 403. Documented in `run_playbook.md` Sec.3 so it isn't mistaken for a
new leak if your environment (or a CI runner, later) hits the same thing -
if you ever see this exact WARN with this exact error text, it's the network,
not the corpus.

Nothing needed from you on any of this right now - flagging it so the shared
picture of "what's true about this repo" stays in sync between sessions,
same reason as every other dated block in this file.

## NEW 2026-07-21 (later still): verified your 4 newest driver-test files, all landed

`test_extract_driver.py`, `test_audit_corpus_driver.py`, `test_match_driver.py`,
`test_validate_threshold.py` - read all 4 in full, ran the whole suite clean
myself (320 tests, 1 intentionally skipped - the `RUN_SLOW_TESTS`-gated real-
embedding-model test in the new `validate_threshold` file - `OK (skipped=1)`).
All 4 were already committed by the time I checked (`git status` clean,
`git ls-files` confirms all 4 tracked) - nothing left for me to do on this
batch. Good catches worth calling out: the `audit_project` FAIL-beats-WARN-
beats-PASS aggregation tests, and pinning `extract.py --all`'s "always exits
0 regardless of skip count" as a characterization rather than silently
"fixing" it - that's a real design wart but changing it is a scope decision,
not a bug fix, and you were right to just document it instead.

## Task F: 11 new tasks, all pre-approved, same ground rules as always

Madhu asked for a fresh batch, at least 10. Below are 11, ordered roughly by
value. All of these are engineering/testing/documentation only - none of
them touch rater outreach (that's Task E territory, explicitly on hold until
Madhu says otherwise), none need real API keys or `.env`, and none invent
data, dates, or citations. Normal rule still applies: if any of these turns
up something that looks like it needs a decision beyond "write code/tests/
docs", stop and flag it rather than guessing - same as the Task E lesson
about unrequested scope creep.

**F1 - close the real gap in `run_experiments.py`'s synchronous CLI.**
Confirmed by grep just now: the only `rx.main()` calls anywhere in the test
suite are the 4 in `test_batch.py`, and every one of them exercises a
`--batch`/`--batch-check` combination. The plain synchronous grid loop's own
two exit paths - `sys.exit(2)` when every cell fails, `sys.exit(3)` when some
(not all) fail - have zero coverage anywhere (`grep -rn "sys.exit(2)\|sys.exit(3)"
tests/*.py` finds nothing for this path; the one `.code, 2)` hit in
`test_batch.py` is the argparse mutual-exclusion error, a different thing).
New `tests/test_run_experiments_driver.py`: cover `--project`/`--model`/
`--prompt` filtering actually narrowing the grid, `--estimate-only`
short-circuiting before any `run_one()` call, and all three outcomes (all
succeed / all fail -> exit 2 / partial fail -> exit 3) with a stubbed
`run_one`.

**F2 - close `metrics.py`'s zero CLI coverage.** Confirmed: no
`class Test.*CLI`/`Test.*Main` in `test_metrics.py`, no direct `metrics.main(`
call anywhere. New `tests/test_metrics_driver.py`: `--scored-dir`/`--out`
parsing, confirm `--out` actually writes the file (vs. stdout-only when
omitted), behavior on an empty or missing scored-dir.

**F3 - close `build_rater_packets.py`'s zero CLI coverage.** Confirmed: the
only "`.main(`" match in `test_rater_packets.py` is the file's own
`unittest.main()` test-runner boilerplate - all 7 existing test classes test
the sampling/blinding logic directly, never the CLI entry point itself. Add a
CLI test class covering `--min-uk-per-cell`/`--raters` parsing, output file
writes, and exit codes.

**F4 - retry/backoff for transient errors in `call_claude`/`call_gpt`/
`call_opensource`.** A 189-cell grid at real spend shouldn't need a human to
notice and manually re-run one flaky timeout/5xx/rate-limit. 2-3 attempts,
exponential backoff, only for network-level/5xx/rate-limit errors - a genuine
4xx/auth error should still fail immediately (retrying a bad key wastes time
and money, and would mask a real setup problem). New tests: a fake provider
that fails N times then succeeds, and one that fails permanently and still
surfaces the error. Flagging this one for extra care since it's the actual
live-request path - go ahead, no need to check back first, just double-check
the retry doesn't accidentally swallow or mask the auth-error case.

**F5 - synthetic demonstration of `pretraining_cutoff_report()`'s output.**
Same synthetic-fixture pattern `analysis/gen_synthetic_scored.py` already
uses. Use CLEARLY-LABELED placeholder cutoff dates (filename prefix + an
in-file banner comment saying "SYNTHETIC PLACEHOLDER - not a real model
fact"), not real ones - the only point is showing Madhu/Kruthik the report's
actual shape before real `model_cutoffs` exist. Must not be mistakable for
real data anywhere it might get read later.

**F6 - research task (web search, not fabrication): real published training
cutoff dates for the 3 decided models.** Claude Sonnet 5, GPT-5.6 Terra,
Llama 3.3 70B Turbo - look these up directly from each provider's own
documentation. Write findings into a new `docs/model_cutoffs.md` with exact
source URLs and the date you looked it up. Do NOT wire this into any code -
reference documentation only, so whoever runs `pretraining_cutoff_report()`
for real has the sourcing ready without the function ever hardcoding a date.
If a provider hasn't published an exact cutoff, say that explicitly rather
than guessing or extrapolating from a model-card release date.

**F7 - `requirements.txt` vs. actual-imports consistency test.** Same spirit
as the existing `test_env_example.py`, but for Python packages: every
third-party top-level import used anywhere in `src/`/`analysis/` has a
pinned line in `requirements.txt`, and every pinned package is actually
imported somewhere (no stale/unused pins). I spot-checked this by hand just
now and it currently looks consistent - this task is about building the
permanent automated guard, not necessarily finding an existing bug.

**F8 - a "CLAUDE.md compliance" self-check test file.** Static assertions
tying live code/schema constants to CLAUDE.md's actual written numbers, so a
future silent drift gets caught by CI instead of by someone re-reading both
documents by hand (how most of this session's real bugs were actually
found). Concretely: cost-guard threshold == $30 (may partly exist in
`test_run_pipeline.py` already - extend rather than duplicate), the
`category` enum in `prompts/output_schema.json` matches CLAUDE.md's exact 8
categories with no extras or omissions, likelihood/impact are both 1-5, and
the documented repo-structure directories actually exist on disk.

**F9 - document (don't touch) `proposed_excision_pages`.** I checked this
myself already: `extract.py` never reads this column (confirmed by grep) -
it derives excision entirely from `sort_pages` + `section_v_pages`. Reading
a few rows, `proposed_excision_pages` looks like a deliberate, valuable
human-readable audit trail (e.g. the Peru p32-33 / Uganda p78-79 entries
explain *why* each range was added), not dead weight. Please confirm that
reading holds across all 21 rows and add one short line (manifest header
comment or a `methodology_notes.md` note) stating explicitly that this
column is narrative/audit-only and deliberately not machine-read - so nobody
"cleans it up" later thinking it's vestigial. Do not remove, rename, or
restructure the column itself.

**F10 - a "playbook smoke test."** A new test file that actually runs every
command in `docs/run_playbook.md`'s quick-start sequence end-to-end against
tiny stubbed fixtures (same conventions already established: fake provider
modules, sandboxed temp-tree run). This exact bug class - doc says X, code
does Y - has now bitten this project at least 3 times this session alone
(the `--confirm-cost` doc claim, and two separate `relative_to(REPO_ROOT)`
crash-on-relative-path bugs). This test should fail loudly the next time a
code change silently breaks a documented command.

**F11 - stale cross-reference sweep for the batch-API addition.** Check
whether `docs/rater_protocol.md`, `results/threshold_validation_report.md`,
`paper/methodology_notes.md`, or any other already-written doc makes claims
about `run_experiments.py`'s behavior (timing, cost, "one call per cell"
assumptions) that are now inaccurate given `--batch`/`--batch-check`. Report
findings; only fix a claim that's actually wrong, don't rewrite sections that
are still accurate.

All 11 are pre-approved - no need to check back before starting any of them.
If you finish all 11 and want still more, ask before expanding scope
further, same rule as always.

## Ground rules (same as always, from CLAUDE.md)

- Never commit `data/raw/` or `.env`.
- Don't touch the frozen RQs or the leakage rule.
- Task E is done and stays done - rater recruitment outreach itself
  (actually contacting people) is explicitly on hold until Madhu says
  otherwise. Don't touch `docs/rater_recruitment_outreach.md` or send
  anything on Madhu's behalf as part of Task F.
- The git backlog mentioned in earlier handoffs is resolved - everything's
  committed now, working tree was clean before this round of tasks started.
  I'm still committing your work from the Cowork side as it lands, same as
  before - nothing you need to do differently.
- Task F (all 11 items above) is pre-approved - no need to check back before
  starting any of them. If you finish all 11 and want still more, ask before
  expanding scope further.
