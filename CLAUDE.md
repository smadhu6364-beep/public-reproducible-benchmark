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
    paper/               (Overleaf-linked, not stored here)

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
