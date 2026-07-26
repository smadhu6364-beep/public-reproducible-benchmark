Project: LLM Risk Register Benchmark (IEEE Paper)

## What this repo is

Code and data for an independent IEEE conference paper:
"Evaluating Large Language Models for Automated Risk Register Generation
from Project Documentation: A Benchmark Study"

Authors: Madhu (pipeline, experiments, metrics) and Kruthik (lit review,
evaluation protocol, raters, writing). Target: IEEE TEMS-family conference,
submission ~Feb-Mar 2027. IEEE two-column format, 6-8 page limit.

## Research questions (FROZEN - never modify or reinterpret)

RQ1: How complete/accurate are LLM-generated risk registers vs. human-authored ones?
RQ2: How do results vary across 3 models (one general-purpose proprietary
model and two distinct open-weight models) and 3 prompting strategies
(zero-shot, few-shot, structured reasoning)?
RQ3: Which risk categories do LLMs systematically miss or hallucinate?
(Failure-mode analysis = the paper's core contribution.)

> **SUPERSEDED 2026-07-23 (Madhu) - this is the first change to this frozen
> section in the project's history, so the original is preserved here
> verbatim, not silently dropped:**
>
> > RQ2: How do results vary across 3 models (Claude, GPT, one open-source) and
> > 3 prompting strategies (zero-shot, few-shot, structured reasoning)?
>
> **Why it changed:** on the first real spend attempt, all three
> originally-decided provider accounts (Anthropic, OpenAI, Together AI) hit
> real billing/quota errors - none had funded billing (`400` credit-balance-
> too-low, `429` insufficient_quota, `402` credit-limit-exceeded
> respectively). Rather than pay, Madhu chose to redesign the model lineup
> around 3 genuinely free-tier models instead: Google Gemini
> (`gemini-2.5-flash`, a lighter/Flash-tier model, not Google's flagship -
> named plainly since the original slot was a flagship-tier model) plus two
> distinct open-weight models served via Groq's free tier
> (`openai/gpt-oss-120b` and `qwen/qwen3.6-27b`) - see
> `docs/model_tier_recommendation.md`'s dated addendum for the full reasoning
> and exact model IDs/base URLs. **This decision briefly produced two
> conflicting instructions given to two different Claude sessions within
> minutes of each other** (this free-tier swap vs. a separate "keep the paid
> triple, cut to 1 run" instruction given in parallel) - flagged directly,
> and Madhu gave one final, singular answer: proceed with the free swap. Not
> a rubber-stamp - given with full knowledge of the real concerns raised
> (rate limits and ToS sourced from aggregator sites rather than primary
> documentation at the time of the original proposal, since corrected;
> `gpt-oss-120b` being OpenAI's open-weight model rather than proprietary GPT
> access, so the "GPT slot" name is a role label, not a literal claim of
> equivalence; Gemini's free-tier data-usage terms, below).
>
> **Real, disclosed change to the comparison's shape** (2 proprietary + 1
> open-weight became 1 proprietary + 2 open-weight), not a relabeling of the
> same categories - state it explicitly in the paper's Methodology/
> Limitations sections, not only here.
>
> **Gemini free-tier data-usage note, primary source
> (ai.google.dev/gemini-api/terms), not an aggregator:** Google states it uses
> "Unpaid Services" (free-tier) input/output "to provide, improve, and develop
> Google products and services," and that human reviewers may read/annotate
> API input and output; this protection against training-use does NOT extend
> to the free tier the way it does to paid tiers. Since the planning documents
> sent as input are already-public World Bank/UK documents, this is a lower-
> stakes concern than it would be for confidential data, but it is a real,
> disclosable fact for the paper's ethics/limitations section, not something
> to silently accept.
>
> **Groq rate limits: genuinely unresolved, not asserted as fact.**
> Aggregator sources claimed 14,400 requests/day org-wide; Groq's own
> models-list page shows different, model-specific numbers for the exact
> models chosen here under a "Developer Plan" label whose relationship to the
> actual free tier isn't clear from the page alone. Verify directly in the
> Groq console once a real account exists - don't trust either source
> blindly before a real run.
>
> **FURTHER UPDATE 2026-07-23 (later the same day) - the Groq question above
> is now resolved, and the answer forced a second change:** the first real
> scoped smoke test (not a toy call - a genuine ~30K-token corpus prompt)
> confirmed Groq's free tier has a hard, structural 8,000 TPM per-request cap
> on both `openai/gpt-oss-120b` and `qwen/qwen3.6-27b` (verified directly
> against console.groq.com/docs/rate-limits, not an aggregator) - this
> project's real prompts run ~30-34K tokens, ~4x over. Not a pacing/retry
> problem: a single request this size is rejected outright regardless of
> backoff, and even Groq's other free models cap at 12K TPM, so staying
> within Groq's catalog doesn't fix it. The `gpt` and `opensource` slots
> moved to **SambaNova Cloud** instead (api.sambanova.ai, OpenAI-compatible,
> no card required, confirmed via docs.sambanova.ai/docs/en/models/rate-limits:
> 20 RPM / 20 RPD / 200,000 TPD per model, no TPM/per-request wall). `gpt`
> keeps the exact same `openai/gpt-oss-120b` model (no further comparison-
> shape disclosure needed for that slot); `opensource` reverts from Qwen to
> **`Meta-Llama-3.3-70B-Instruct`** - this project's ORIGINAL pre-redesign
> open-source pick, back in service because it's already on SambaNova's free
> tier and Qwen genuinely is not. RQ2's actual wording above ("two distinct
> open-weight models") still holds unchanged - this is a provider and
> specific-model correction, not a further change to the comparison's shape.
> Real-call verified before this was wired in, not just docs-page arithmetic:
> a genuine ~28,400-token corpus prompt succeeded against both models
> (`Meta-Llama-3.3-70B-Instruct` cleanly; `openai/gpt-oss-120b` needed
> `max_tokens>=4096` to clear its own hidden reasoning-token spend first, the
> same class of behavior as Gemini's "thinking tokens" below). Two candidate
> alternatives (Cerebras, OpenRouter) were checked against primary sources and
> ruled out first - see `docs/model_tier_recommendation.md`'s dated addendum
> for why. **Not resolved:** SambaNova's responses expose no rate-limit
> headers at all, so whether its 200,000 TPD/model budget is independent per
> model or shared account-wide - materially affecting whether the full
> 21-project grid takes ~21 or ~42 days - remains genuinely unknown until a
> real multi-day run is tried.
>
> **SambaNova free-tier data-usage: genuinely unaddressed, not confirmed
> either way.** Checked SambaNova's own privacy policy directly
> (sambanova.ai/privacy-policy) - it does not specifically state whether
> prompts/outputs sent to SambaNova Cloud's serverless API (particularly the
> free tier) are used for model training/improvement or human review.
> Marketing material makes a general "we don't collect your data" claim, but
> that framing appears tied to their dedicated/enterprise offering, not
> clearly to the public free-tier Cloud API, and SambaNova's own developer
> community has an open, unanswered request asking the company to clarify
> exactly this point for serverless inference. State this honestly in the
> paper's ethics/limitations section as an open question, not as either a
> confirmed protection or a confirmed risk - unlike Gemini's free tier, where
> the data-usage terms are at least explicit (if unfavorable).
>
> **REAL FULL-GRID ATTEMPT 2026-07-23: the daily-quota question above is now
> answered, and it's more severe than any prior estimate.** Ran the real
> 189-cell x 2-run grid (378 calls) for the first time. Result: **13
> succeeded, 365 failed** - all three providers hit hard daily quotas almost
> immediately, not a pacing problem retry/backoff can smooth over. Real,
> disclosed findings, not docs-page arithmetic:
>
> - **Gemini's real daily cap is 20 requests/day**, not the 1,500/day
>   originally researched (that figure was for a different Gemini
>   generation) - confirmed directly from the real 429 error body:
>   `quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`,
>   `quotaValue: '20'`, against whatever model `gemini-flash-latest`
>   currently resolves to (the error names it `gemini-3.6-flash` - useful,
>   unplanned confirmation of what that rolling alias points to today,
>   though `docs/model_cutoffs.md`'s cutoff research still needs re-checking
>   against that exact name). 11 of 63 needed Gemini cells cleared before the
>   day's quota was gone.
> - **SambaNova's 200,000 TPD budget is confirmed independent per model**
>   (`gpt` and `opensource` reported different `Current usage: X of 200000`
>   figures at the same wall-clock time) - resolves the "shared vs.
>   independent" question left open above, in the more favorable direction
>   (each model gets its own budget, not one pooled between them). Only 1
>   `gpt` and 1 `opensource` cell cleared today, but that figure is
>   artificially low: this same session's own earlier real-call verification
>   and diagnostic testing (confirming the SambaNova fix, finding the
>   `max_tokens` truncation bug) already consumed most of today's 200K/model
>   budget before the full-grid attempt even started - a clean day should
>   clear closer to the ~6-7 calls/model/day the TPD math predicts.
> - **Real projected timeline: roughly 3 weeks of daily re-runs** to clear
>   the full grid, bounded by SambaNova's slower models (126 calls needed
>   each at ~6-7/day) rather than Gemini (63 calls needed at ~11-20/day,
>   finishes in under a week). Madhu's explicit decision (2026-07-23): accept
>   this timeline rather than cut runs or pay - re-run
>   `python src/run_experiments.py --runs 2` daily; the pipeline safely
>   resumes (raw outputs are append-only, `next_free_run_index` skips
>   completed cells) rather than needing anything special per re-run.
>
> **ADDENDUM 2026-07-25/26: a real, small paid spend entered the pipeline
> via an OpenRouter fallback, added without prior sign-off - retroactively
> authorized 2026-07-26, documented here so it isn't a silent change to the
> "genuinely free-tier" design above.** SambaNova's real daily caps
> (~6-7 calls/day/model) are the actual bottleneck on the 3-week timeline
> above, not something retry/backoff can fix. A same-day change (Cowork
> session, commit `6653857`) added OpenRouter as a fallback for the `gpt`/
> `opensource` slots: `call_gpt()`/`call_opensource()` now fall through to
> OpenRouter only when SambaNova raises a transient (rate-limit/5xx) error
> and `OPENROUTER_API_KEY` is configured; a non-transient error still
> propagates immediately, and behavior is unchanged when the key isn't set.
> Real-call verified against a genuine ~35,100-token corpus prompt: both
> `openai/gpt-oss-120b` and `meta-llama/llama-3.3-70b-instruct` succeed on
> OpenRouter - the same exact models this project already uses, so this is
> a provider addition, not a further change to RQ2's comparison shape.
>
> **This is real, disclosed paid spend, not free-tier.** OpenRouter's own
> `:free`-suffixed tier does not include either exact model (confirmed
> against their live models API); calls route to the real, paid versions at
> roughly $0.000000037-0.0000004/token (~$0.002-0.006 for a ~35K-token
> call). The first live run under this fallback (commit `d114dca`) made 46
> real calls before hitting a genuine `402 Payment Required` - the account's
> implicit trial balance (confirmed via `/api/v1/key`'s usage field
> climbing from \$0 to \$0.1814 across the run) was spent, not a rate limit.
> Two things flagged as genuinely unconfirmed rather than asserted: how a
> \$0-lifetime-purchase account is able to pay for a non-free model at all,
> and whether OpenRouter's documented 50-req/day free-tier cap applies the
> same way to these paid-model calls. Real total impact so far: roughly
> \$0.18 spent, once.
>
> **Why this needed a addendum and not just a commit message:** every other
> provider/model decision in this section - the original free-tier redesign,
> the Groq to SambaNova move - was free-tier-to-free-tier and got a dated
> writeup here before or immediately after landing. This one crossed from
> genuinely-free to a real (if tiny) paid call automatically, on a daily
> cron Madhu isn't watching live, without going through that same disclosure
> step first. Raised directly to Madhu 2026-07-26 (VS Code session) rather
> than left as an implicit fact buried in a commit message; **Madhu's
> decision: keep the fallback active, retroactively authorized, documented
> here** rather than capped or reverted. The paper's Methodology/Limitations
> sections must describe the pipeline as free-tier-with-a-small-paid-
> fallback from this point forward, not as purely free-tier.

## Methodology rules (enforce in all code you write)

- Corpus: ~20 real projects with BOTH public planning docs AND a published
  human risk register. Sources: World Bank Project Appraisal Documents (PADs),
  UK IPA/GMPP reports.
- LEAKAGE RULE (critical): models only ever receive planning/appraisal
  documents. The file containing the real risk register must never enter a
  prompt, a context window, or a few-shot example drawn from the same project.
- Grid: 3 models x 3 prompts x 20 projects, 2-3 runs each, temperature 0-0.2.
- Reproducibility: every run logs model version string, run date, temperature,
  prompt file SHA256, into results/run_config.jsonl.
- Raw model outputs in results/raw_outputs/ are append-only. Never overwrite.
- Output schema (fixed JSON per risk): risk_id, description, category
  (technical | financial | schedule | stakeholder | political_regulatory |
  environmental | organizational | external), likelihood (1-5), impact (1-5),
  mitigation.
- Evaluation: (A) semantic matching vs. ground truth - recall, precision,
  per-category coverage; (B) expert Likert ratings + Fleiss' kappa;
  (C) LLM-as-judge, supplementary only.

## Repo structure (maintain exactly)

    data/raw/            original PDFs (gitignored)
    data/processed/      extracted text per project
    data/ground_truth/   human risk registers as structured JSON
    data/corpus_manifest.csv
    prompts/             zero_shot.txt, few_shot.txt, structured.txt, output_schema.json
    src/                 extract.py, run_experiments.py, match.py, metrics.py, judge.py
    results/raw_outputs/ (append-only)
    results/scored/
    analysis/figures/
    paper/               (tracked in this repo - corrected 2026-07-23, Madhu:
                          the original "Overleaf-linked, not stored here"
                          annotation was wrong as of F8's compliance check,
                          which found real paper/main.tex content already
                          committed here. Decision: keep it in the repo,
                          fix the note rather than migrate - stays this way
                          unless a future migration to Overleaf is decided.)

## Coding standards

- Python 3.11+, venv, requirements.txt pinned versions.
- Libraries: PyMuPDF (pdf extraction), anthropic, openai, sentence-transformers,
  pandas, scikit-learn, matplotlib. Ask before adding anything else.
- API keys only via .env (python-dotenv). .env is gitignored; keep .env.example updated.
- Small, reviewable commits with clear messages. Never commit data/raw or .env.
- Cost guard: before any full-grid run, print a token/cost estimate and STOP
  for confirmation if projected cost > $30.

## Hard rules

- Never fabricate data, citations, metrics, or results. Unknown = say unknown.
- Never expand scope (extra models, metrics, datasets) without asking first.
- Timeline: corpus + pipeline + full experiment run must complete by end of
  August 2026. Prefer working code today over elegant code next week.
