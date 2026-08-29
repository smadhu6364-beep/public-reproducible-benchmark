# Methodology Log

Dated record of methodology decisions, deviations, and disclosed
limitations for the LLM Risk Register Benchmark project. Written for the
paper's Methodology and Limitations sections, and kept here so the
reasoning behind each decision has a citable record independent of git
history.

## Model lineup

The original design compared three paid proprietary/commercial APIs. On
the first real spend attempt, none of the three provider accounts had
funded billing, so the lineup was redesigned around free-tier options:

- **"claude" slot:** Google Gemini (`gemini-flash-latest`), via its
  OpenAI-compatible endpoint. This slot name is a historical label from
  the original design, not a literal claim; the paper's Methodology
  section states plainly that this slot is served by Gemini, not by
  Anthropic's Claude.
- **"gpt" slot:** `openai/gpt-oss-120b`, served via SambaNova Cloud
  (moved off Groq after Groq's free tier proved unable to serve this
  project's roughly 30K-token prompts under its 8,000 TPM cap). A
  same-day OpenRouter fallback was added for transient provider errors;
  this introduced a small amount of real paid spend (approximately $0.18
  total, disclosed below).
- **"opensource" slot:** `Meta-Llama-3.3-70B-Instruct`, served via
  SambaNova Cloud.

RQ2 as stated in the paper describes the comparison as "one
general-purpose proprietary model and two distinct open-weight models"
rather than naming specific vendors, so the wording stays accurate
through this provider-level change.

## Known deviation: temperature handling on the "gpt" slot

OpenAI's GPT-5 reasoning-family API rejects the legacy `max_tokens`
chat-completions parameter and, in reasoning mode, may reject
`temperature` outright. `call_gpt()` sends `max_completion_tokens` and
retries without `temperature` if the API rejects it, logging a
`temperature_applied` field on the raw output record and in
`results/run_config.jsonl` rather than assuming uniformity held across
all three models. This is disclosed in the paper's Limitations section
as a possible deviation from temperature-controlled comparison.

## Corpus

21 projects included: 18 World Bank Project Appraisal Documents plus 3 UK
government business cases (HyNet CCUS, Padeswood CCUS, Free Breakfast
Clubs). Two UK candidates were excluded with documented reasoning
(Sizewell C: no itemized risk register anywhere in the document; Connect
to Work: a real but degenerate register with only 2 risks, no mitigation
content, and no category diversity). One World Bank project is set aside
as a labeled outlier. Full inclusion/exclusion criteria and per-project
reasoning are in `INCLUSION_CRITERIA.md` and `data/corpus_manifest.csv`.

Three real bugs were found and fixed during corpus preparation, each
caught by directly re-checking source PDFs page by page rather than
trusting a recorded page range: a systematic table-of-contents
under-excision affecting 8 World Bank documents, an over-excision on the
Uganda project that wrongly cut 9 legitimate planning pages, and a
page-offset error on the HyNet project (every recorded page off by 2,
missing two risk-bearing sections). All three are fixed and independently
re-verified. `src/audit_corpus.py` is kept as a permanent leakage/range
scan to re-run whenever the corpus changes.

## Matching threshold validation

The semantic-matching threshold (`MATCH_THRESHOLD` in `src/match.py`) was
validated against 17 hand-labeled project-pair examples (World Bank, UK,
and cross-project hard cases) plus 4 borderline cases reported
separately, run through the `all-MiniLM-L6-v2` embedding and
cosine-similarity pipeline at a threshold sweep. Should-match pairs
scored 0.52-0.81; should-not-match pairs scored 0.20-0.42, a clean
separation. The threshold was lowered from 0.50 to 0.45 to sit just above
the lowest true positive, recovering legitimate granularity-mismatch
matches that 0.50 was clipping.

## Rater protocol (Method B) - formally descoped 2026-08-18

Sampling, blinding, and per-rater packet assignment are seeded and fully
reproducible; the packet-generation pipeline never reads
`data/ground_truth/`, preserving the leakage guard. UK representation
across the sampled set is enforced at a minimum of 1 UK register per
cell, covering all 9 risk-category cells across the full 45-item sample.

Recruitment of the 3-5 practitioner raters themselves (real project
management experience on complex or public-sector-scale projects) never
progressed past the ready-to-send outreach draft
(`docs/rater_recruitment_outreach.md`) - confirmed directly (not assumed)
on 2026-08-18 that no outreach had gone out and no rater data exists
anywhere. Given the Aug-2026 timeline, Method B is formally descoped from
the paper rather than left as an indefinite placeholder: the paper is now
scoped as a fully automated evaluation (Method A primary, Method C
supplementary), with Method B's absence disclosed directly in the
Methodology, Discussion/Limitations (renamed "Method B Descoping"), and
Future Work sections, not silently dropped. The built protocol, sampling
code (`src/build_rater_packets.py`), and kappa computation
(`src/compute_kappa.py`) are untouched and still tested - only the paper's
framing changed - so a future replication with real recruiting capacity
does not have to rebuild any of it. See `docs/rater_recruitment_channels.md`
and `docs/rater_recruitment_outreach.md` for the recruitment materials that
were never sent.

## Method C (LLM-as-judge) - real pilot run, 2026-08-18

`src/judge.py` had only ever been exercised against mocked provider
responses; on 2026-08-18 it was run for real, for the first time, against
five real generated registers from `results/raw_outputs/`. This was a
deliberately small feasibility pilot, not the full grid, gated by the same
free-tier daily quota (Table `tab:quotas` in the paper) that governs the
main generation grid, since the configured judge
(`JUDGE_MODEL_LABEL=claude` in `.env`, i.e. Gemini) shares that 20
request/day cap.

Pilot files were drawn only from `gpt-oss-120b`- and
Llama-3.3-70B-generated registers, deliberately excluding
Gemini-generated ones, to sidestep the self-preference-bias risk
`judge.py`'s own docstring already flags (the judge model is one of the
three benchmarked models). Note this only defers the problem for a
full-scale run: the Gemini-generated third of the corpus would still be
self-judged unless a fourth, non-benchmarked model is wired into
`MODEL_DISPATCH` as judge, which does not currently exist.

Result: 2 of 5 calls (40%) returned a valid, parseable score (both
`gpt-oss-120b`/zero-shot, scored completeness 5/5, accuracy 5/5,
actionability 4/5 and 5/5, overall 5/5 - too small and too narrow a
sample to support any model-comparison claim). The other 3 (60%) failed to
parse: inspecting the raw responses directly, 2 were truncated mid-JSON
(cut off after 2-3 score fields, before the closing brace or rationale)
and 1 returned an empty string. This is the same hidden-reasoning-token
truncation phenomenon already disclosed for the main generation grid, but
here hitting `judge.py`'s own separate, smaller, hardcoded 512-token
output budget. A 60% truncation-driven failure rate in this pilot means
that budget needs to be enlarged before a full-scale Method C run would be
worth attempting - logged here as an actionable follow-up, not fixed in
this pass, so the code that produced this real pilot data isn't silently
changed out from under it. Raw pilot outputs: `results/scored_pilot/`
(5 files). Full writeup: paper's Method C Results subsection.

## Real cost and data-usage disclosures

- **Total real spend to date: approximately $0.18**, via the OpenRouter
  fallback described above. All other provider usage (Gemini, SambaNova)
  is within free tiers.
- **Gemini free-tier data usage:** per Google's published terms
  (ai.google.dev/gemini-api/terms), free-tier input and output may be
  used to improve Google's products, and human reviewers may read or
  annotate API input and output. This protection gap versus paid tiers
  does not extend to this project's inputs. Because the planning
  documents used as input are already-public World Bank and UK
  government documents, this is a lower-stakes concern than it would be
  for confidential data, but it is disclosed here and in the paper's
  ethics and limitations section rather than assumed away.
- **SambaNova free-tier data usage:** genuinely unconfirmed either way as
  of this writing. SambaNova's published privacy policy does not
  specifically address whether prompts and outputs sent to its free-tier
  serverless API are used for training or human review. Stated in the
  paper as an open question, not a confirmed protection or risk.

## Current status

392 scored result files exist across all 21 projects and all three model
slots (138 in the "claude"/Gemini slot, 127 "gpt", 127 "opensource"),
against a target grid of 3 models x 3 prompts x 21 projects x 2-3 runs
(189-567 cells). Real-world daily quota limits on the free-tier providers
mean the full grid is being completed through repeated re-runs rather
than a single pass; the pipeline resumes safely between runs since raw
outputs are append-only and already-completed cells are skipped
automatically.
