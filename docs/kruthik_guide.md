# Guide for Kruthik: what's actually left to do

Written 2026-07-28, for Madhu to hand to Kruthik. This reflects the real,
current state of the repo, not just the original role split in
`PROJECT_SPEC.md`. A lot of the lit review and paper drafting is already
done, so this guide says plainly what still needs a human, and what
doesn't.

**Project in one line:** benchmarking 3 LLMs across 3 prompting strategies
on generating project risk registers from planning documents, checked
against real published human-authored registers. Corpus and pipeline are
done; the experiment grid is ~98% complete as of today. Submission target
is an IEEE TEMS-family conference, roughly Feb-Mar 2027. There's real
runway after the pipeline finishes; this isn't a today-or-never situation
except for the one item below with its own lead time.

`PROJECT_SPEC.md` lists Kruthik's areas as: lit review, evaluation protocol,
raters, writing. Here's the real status of each.

---

## 1. Rater recruitment: the one thing that's genuinely, only, on you or Madhu

**Status: not started. This is the actual bottleneck on the whole paper.**

Everything else about Method B (the human-expert evaluation) is built and
tested: the scoring protocol, the sampling (45 registers, blinded, seeded),
the packet-generation script, and four blank scoring sheets sitting ready
(`results/rater_packets/rater_assignments/rater1.csv` through `rater4.csv`).
What's missing is real people to fill them in.

**What you need to do:**
1. Find 3-5 people with real project management experience, ideally on
   complex, multi-year programmes (infrastructure, energy, public-sector,
   or international development work is the closest match to this study's
   corpus, but not a hard requirement). They do **not** need any AI/ML
   background; the opposite is the point.
2. Send them the ready-to-send message in
   `docs/rater_recruitment_outreach.md`. It's fully drafted; you only fill
   in `[Name]`, `[DATE]`, and confirm the `[Madhu]` sign-off. Don't rewrite
   it from scratch, it's already been through a few iterations.
3. The ask is honest and upfront in the message: ~4-6 hours of their time,
   volunteer (no budget attached), reviewing 45 short packets and scoring
   each on three simple 1-5 questions.

**Why this has real lead time, unlike the other items:** warm-network asks
(people you or Madhu already know) can close in days. Cold outreach
(LinkedIn, professional bodies like PMI/APM) realistically takes 1-3 weeks
and a lot of messages for a modest reply rate. Start this first, in
parallel with anything else below; it's the one task on this list where
waiting costs real calendar time.

---

## 2. Evaluation protocol: mostly already decided, one soft-open item

**Status: essentially done.** `docs/rater_protocol.md` is the full protocol
(what raters see, the 3-dimension Likert scale, blinding, how kappa gets
computed); it's implemented in code (`src/build_rater_packets.py`,
`src/compute_kappa.py`, both tested), not just a design doc. Two decisions
that used to be open are resolved: raters are volunteer/unpaid, and
delivery is a spreadsheet (matches what the script already produces).

**One thing worth 5 minutes of your attention, not a blocker:** the sample
size (45 registers total: 5 projects × 9 model/prompt combinations, same
45 rated by every rater) was picked as a reasonable trade-off between
statistical power and rater time, but the doc flags it as "the part most
likely to need Madhu/Kruthik revision." If you think 45 is too many or too
few given real recruiting difficulty, say so; otherwise the current
default just runs.

---

## 3. Literature review: a full draft exists, worth a real read-through

**Status: substantially drafted, not empty.** The paper's Related Work
section is ~1,000 words across six subsections (AI in project management,
LLMs for project risk management specifically, risk classification vs.
generation, prompting-strategy literature, LLM evaluation methodology, and
benchmarking/inter-rater precedent), plus a positioning table naming six
concrete gaps in prior work and how this study addresses each. All 26
citations in `paper/references.bib` have been individually verified against
primary sources (arXiv pages, DOIs, publisher pages) as of today: author
lists, venues, and pages checked, not just pulled from a search result.

**What's actually left for you here:**
- **Read it as a domain expert, not a copy-editor.** Does the framing
  match how you'd actually describe this field? Is anything mischaracterized,
  overstated, or missing a paper you know should be there? This is exactly
  the kind of judgment call that needs a real domain expert's eye.
- **~5 entries in references.bib are still incomplete**, mostly
  volume/page numbers for a few MDPI/ScienceDirect articles that wouldn't
  load during lookup, plus one entry whose venue type (journal article vs.
  book chapter) needs confirming. Each has a `TODO:` note explaining
  exactly what's missing and what was already tried; search
  `references.bib` for `TODO` to find them.
- **The Positioning table's claims are worth a sanity check.** It asserts
  specific gaps in prior work (e.g., "no public, reproducible benchmark
  exists"). You know this literature firsthand; if any claim there is too
  strong or slightly wrong, flag it before submission.

---

## 4. Writing: most of the skeleton exists; the real gaps are specific

**Status: ~9 pages compiled, Introduction/Related Work/Methodology/most of
Discussion done. Results, Abstract, and Conclusion are deliberately still
placeholders**, since they can't be honestly written until the experiment
grid finishes and real numbers exist (it's at ~98% now, should close
within days). Writing those sections properly, from real data, is planned
as the next step once the grid completes, not something to start from a
blank page before then.

**What's genuinely useful from you before that point:**
- Review the Methodology and Discussion sections for tone and accuracy.
  They're long and technical (free-tier infrastructure decisions, leakage
  control, the pretraining-contamination discussion) and would benefit
  from a second set of eyes who isn't the one who wrote them.
- Once Results/Abstract/Conclusion are drafted from real data, that's the
  natural point for you to take a full writing/editing pass across the
  whole paper for voice consistency. Right now most of it reads like a
  first-pass draft built from real project data, which is fine for a
  working draft but not how a finished co-authored paper should read.
- Final IEEE formatting and page-limit compliance (task in the project's
  own tracker) is still open and is naturally a two-author check before
  submission.

---

## Suggested order, given the above

1. **Start rater recruitment now**: it's the only item with real lead
   time, and everything else has slack until the grid finishes.
2. **Read the lit review and positioning table** when you have an hour.
   Low urgency, but the sooner any gaps are caught the better.
3. **Fill in the ~5 remaining references.bib TODOs**, if you have easy
   access to those specific papers (search `references.bib` for `TODO`).
4. **Everything else** (Results/Abstract/Conclusion, final writing pass,
   formatting check) naturally happens once the grid finishes; no need to
   start early.

## Where things live

- `docs/rater_recruitment_outreach.md`: the outreach message, send-ready
- `docs/rater_protocol.md`: the full Method B protocol
- `paper/main.tex`, `paper/references.bib`: the paper itself
- `docs/methodology_log.md`: the methodology decisions, deviations, and
  disclosed limitations, if you want more detail on any specific decision
- `PROJECT_SPEC.md`: the project's frozen research questions and hard
  rules (worth reading once, top to bottom)
