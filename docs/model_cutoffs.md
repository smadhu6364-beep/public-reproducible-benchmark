# Model training/knowledge cutoff dates (F6 research, 2026-07-21)

> **STALE as of 2026-07-23 - do NOT use these dates for a real contamination
> check.** The model tier researched below (Claude Sonnet 5, GPT-5.6 Terra,
> Llama 3.3 70B) was retired the same day this file was written about, for a
> budget-driven reason unrelated to these dates' accuracy - see PROJECT_SPEC.md's
> RQ2 correction note and `docs/model_tier_recommendation.md`'s dated
> addendum. The 3 models actually configured now are Google Gemini
> (`gemini-2.5-flash`), and two Groq-served open-weight models
> (`openai/gpt-oss-120b`, `qwen/qwen3.6-27b`) - none of which have a
> researched cutoff date in this file yet. Re-research all three, the same
> way this file's table below was originally built (direct provider/model-
> card fetch, not a summary), before ever passing a `model_cutoffs` dict to
> `metrics.pretraining_cutoff_report()` against real data from the new
> lineup. Do NOT reuse the dates below for the new models even
> approximately - they are for entirely different models.

Reference data for `metrics.pretraining_cutoff_report(per_run, model_cutoffs, ...)`.
That function deliberately does NOT hardcode any cutoff date in code (PROJECT_SPEC.md's
no-fabrication rule, and the function's own docstring) - it requires the caller to
supply `model_cutoffs` explicitly. This file is that lookup, done once, with real
citations, so whoever runs the real analysis doesn't have to re-research it from
scratch. **No code reads this file.** It is reference documentation only.

Researched via direct web search and primary-source fetch on 2026-07-21, against
the exact model slugs currently pinned in `.env.example`
(`CLAUDE_MODEL_NAME=claude-sonnet-5`, `GPT_MODEL_NAME=gpt-5.6-terra`,
`OPENSOURCE_MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct-Turbo`). If `.env` ends up
pointing at a *different* model version by the time a real experiment run happens
(a version bump, a different provider tier, etc.), **these dates no longer apply -
re-research before running `pretraining_cutoff_report()` for real.**

## The three dates

| Project slug | Real model | Cutoff | Source |
| --- | --- | --- | --- |
| `claude` | Claude Sonnet 5 (`claude-sonnet-5`) | Training data cutoff: **January 2026** (reliable knowledge cutoff also January 2026 - Anthropic distinguishes the two; both land in the same month for this model) | [Anthropic Claude Platform Docs - Models overview](https://platform.claude.com/docs/en/about-claude/models/overview), retrieved 2026-07-21 (official "Latest models comparison" table) |
| `gpt` | GPT-5.6 Terra (`gpt-5.6-terra`) | Knowledge cutoff: **February 16, 2026** | [OpenAI Developers - GPT-5.6 Terra model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra), retrieved 2026-07-21 (states "Feb 16, 2026 knowledge cutoff" directly on the model's own spec page) |
| `opensource` | Llama 3.3 70B Instruct, served via Together AI as `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Pretraining data cutoff: **December 2023** | [Meta's official model card (meta-llama/llama-models, models/llama3_3/MODEL_CARD.md)](https://github.com/meta-llama/llama-models/blob/main/models/llama3_3/MODEL_CARD.md), retrieved 2026-07-21 ("Data Freshness: The pretraining data has a cutoff of December 2023"; table also lists "Knowledge cutoff: December 2023") |

## Notes and caveats

- **The "Turbo" suffix is a serving optimization, not a retrain.** Together AI's
  own model pages and independent coverage describe "Turbo" as FP8-quantized
  inference for speed, not a different training run - so the base Llama 3.3 70B
  model's December 2023 cutoff applies unchanged to the Turbo-served version this
  project actually calls. Confirmed via search, not assumed.
- **Two of the three sources only publish month-level precision**, not an exact
  day (Claude Sonnet 5: "January 2026"; Llama 3.3: "December 2023"). Only GPT-5.6
  Terra's page states an exact day (February 16, 2026). When building a
  `model_cutoffs` dict for `pretraining_cutoff_report()`, which expects an
  ISO date string per model, a defensible convention is to use the **first day**
  of the published month for the two month-only sources - this is a conservative
  choice (it treats the model as if its training data cutoff were as *early* as
  possible within the stated month), not a fabricated precision:

  ```python
  model_cutoffs = {
      "claude": "2026-01-01",       # January 2026 - month-level precision only
      "gpt": "2026-02-16",          # exact day, as published
      "opensource": "2023-12-01",   # December 2023 - month-level precision only
  }
  ```

- **This is a snapshot, not a standing guarantee.** If any of the three `.env`
  model slugs changes before a real experiment run, come back and re-verify -
  do not assume these dates still apply to a different model version.
- `analysis/gen_synthetic_cutoff_report.py`'s demo (F5, same session) deliberately
  uses different, obviously-fake placeholder dates instead of the real ones
  above - seeing what `pretraining_cutoff_report()`'s output shape looks like
  against 100%-fabricated recall/precision numbers should never be dressed up
  with one real-looking fact. The two files are intentionally kept separate;
  neither reads the other.

## Re-research for the new model lineup (2026-07-23)

Following the free-tier redesign (see PROJECT_SPEC.md's RQ2 note), the 3 models
configured at the time were `gemini-2.5-flash`, `openai/gpt-oss-120b` (via
Groq), and `qwen/qwen3.6-27b` (via Groq). Researched directly against primary
sources today - **1 of 3 confirmed, 2 genuinely unresolved**, reported
honestly rather than filled in from the aggregator claims a plain web search
surfaced first.

| Project slug | Real model | Cutoff | Confidence |
| --- | --- | --- | --- |
| `claude` (dispatch key kept for continuity - actually calls Gemini) | `gemini-2.5-flash` | **January 2025** | **Confirmed** - fetched directly from [Google's own model page](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash), retrieved 2026-07-23. States "Knowledge cutoff: January 2025" and "Latest update: June 2025" in an explicit spec table. |
| `gpt` | `openai/gpt-oss-120b` | **Not confirmed** | Checked 3 official OpenAI sources directly - the [OpenAI blog model-card page](https://openai.com/index/gpt-oss-model-card/), the [arXiv abstract](https://arxiv.org/abs/2508.10925) (submitted 8 Aug 2025), and the [Hugging Face model card](https://huggingface.co/openai/gpt-oss-120b) - none of the three states an explicit training/knowledge cutoff date in the content retrieved. A plain web search surfaced a "June 2024" claim from secondary sources, but since it could not be corroborated against any of OpenAI's own pages checked here, it is NOT recorded as fact - do not use it. The full arXiv PDF (not fetched here - large binary) may state it explicitly; worth a follow-up check before this is needed for a real analysis. |
| `opensource` | `qwen/qwen3.6-27b` | **Not confirmed** | Checked Qwen's own official [Hugging Face model card](https://huggingface.co/Qwen/Qwen3.6-27B) in full (architecture, benchmarks, serving instructions, citation) - no training/knowledge cutoff date stated anywhere on the page. Citation gives an April 2026 publication month for the announcement blog, which is a release date, not a training cutoff - do not conflate the two or interpolate a guess from it. |

**Before running `pretraining_cutoff_report()` for real**, either resolve the
two open cells above (check the gpt-oss arXiv PDF directly, check Qwen's
GitHub repo or technical report if one exists) or explicitly mark those two
models as excluded from the contamination sub-analysis rather than guessing
a plausible-sounding date - PROJECT_SPEC.md's "unknown = say unknown" rule applies
here exactly as it did to the Groq rate-limit question.

## SECOND update (2026-07-23, later the same day): Groq -> SambaNova, `opensource` model itself changed

Groq's free tier turned out to have a structural 8K TPM per-request cap this
project's real prompts exceed ~4x (see PROJECT_SPEC.md's RQ2 note) - `gpt` and
`opensource` moved to SambaNova Cloud. This changes what needs researching:

| Project slug | Real model | Cutoff | Confidence |
| --- | --- | --- | --- |
| `claude` | `gemini-flash-latest` (changed from `gemini-2.5-flash` - that ID 404s for new accounts) | **Not re-verified against this specific alias** | The January 2025 cutoff above was researched against `gemini-2.5-flash` specifically. `gemini-flash-latest` is documented by Google as a rolling alias to "the latest stable Flash model" - it may or may not be the exact same underlying model as of any given date. Re-check Google's model page for whichever model `gemini-flash-latest` currently resolves to before trusting January 2025 for a real contamination check; don't assume the alias and the pinned version share a cutoff just because the name is similar. |
| `gpt` | `openai/gpt-oss-120b` | **Not confirmed** (unchanged) | Same model, only the serving provider changed (Groq -> SambaNova) - a model's training cutoff doesn't change with its host, so the "Not confirmed" finding above carries over unchanged. Still worth the arXiv-PDF follow-up noted above if this becomes load-bearing. |
| `opensource` | `Meta-Llama-3.3-70B-Instruct` (changed from `qwen/qwen3.6-27b` - not available on SambaNova's free tier) | **Pretraining data cutoff: December 2023** | **Confirmed** - this is the exact model this project used BEFORE the 2026-07-21 model-tier decision (then served via Together AI as `Llama-3.3-70B-Instruct-Turbo`), so the original F6 research already covers it: [Meta's official model card](https://github.com/meta-llama/llama-models/blob/main/models/llama3_3/MODEL_CARD.md) states "Data Freshness: the pretraining data has a cutoff of December 2023." The "Turbo"/serving-optimization reasoning in this file's Notes section above applies equally here - SambaNova serving the same base weights doesn't change the training cutoff any more than Together AI's Turbo serving did. |

Net effect: 2 of 3 slots' cutoffs are now real, confirmed facts
(`gemini-flash-latest` pending a quick re-check of which model it currently
aliases to; `Meta-Llama-3.3-70B-Instruct` reuses existing, solid research).
Only `openai/gpt-oss-120b` remains genuinely unresolved - resolve it or
explicitly exclude it from `pretraining_cutoff_report()`, per PROJECT_SPEC.md's
"unknown = say unknown" rule, before running the real contamination check.

## THIRD update (2026-07-23): `gemini-flash-latest` re-checked - real cutoff is materially different, not January 2025

PROJECT_SPEC.md's own RQ2 note (the "REAL FULL-GRID ATTEMPT" addendum) already
recorded, from a real 429 error body during an actual full-grid attempt,
that `gemini-flash-latest` currently resolves to **`gemini-3.6-flash`** - not
`gemini-2.5-flash`, the model the January 2025 date above was researched
against. Re-researched directly rather than assume the old date carries over:

| Project slug | Real model | Cutoff | Confidence |
| --- | --- | --- | --- |
| `claude` | `gemini-flash-latest` -> resolves to `gemini-3.6-flash` (confirmed via PROJECT_SPEC.md's real 429 error, not re-derived here) | **March 2026** | **Confirmed** - fetched `ai.google.dev/gemini-api/docs/models/gemini-3.6-flash` directly, which points to the model's official card at `deepmind.google/models/model-cards/gemini-3-6-flash/` (a real PDF, Published July 2026). States plainly under "Known Limitations": "The knowledge cutoff date for Gemini 3.6 Flash was March 2026." Do NOT confuse this with the page's separate "Latest update: July 2026" field - that is a release/refresh date, not a training cutoff, same distinction this file has flagged before for Qwen's announcement date. |

**This supersedes the January 2025 figure in the very first table above for
the `claude` slot specifically** - that figure was real and correctly sourced
at the time, but for a different, now-unused model. January 2025 does NOT
apply to what `.env` actually calls today. March 2026 is barely 4-5 months
before this project's real run - worth flagging plainly in the contamination
analysis, not softened: a cutoff this recent makes contamination against
already-public World Bank/UK planning documents considerably more plausible
than a January-2025 cutoff would have, depending on each document's
publication date (check `corpus_manifest.csv` publication dates against
March 2026 per-project, not just as one aggregate cutoff-vs-corpus
comparison).

## FOURTH update (2026-07-23): `gpt-oss-120b` - still not confirmed by OpenAI directly, one new data point, reported with the right caveats

Checked further while other cutoff gaps were being closed. Found a real,
legitimate academic source this time (not an aggregator blog) -
[LLMLagBench (arXiv:2511.12116)](https://arxiv.org/abs/2511.12116), Pęzik et
al., submitted 15 Nov 2025 - a peer-citable empirical benchmark specifically
built to estimate LLM training cutoffs from behavior, cross-validated against
publicly released information. It reports three different numbers for this
exact model, not one:

- **OpenAI's own declared cutoff: July 2024** (per the paper's own citation of
  OpenAI's stated figure - this is the closest thing to a primary-source
  number found so far, but it is being relayed via this paper's citation, not
  independently confirmed here against an actual OpenAI page. The 3 OpenAI
  sources checked directly in the earlier F6-era research - the model-card
  blog post, the arXiv abstract, the Hugging Face card - still did not surface
  this figure in the content actually retrieved here.)
- **The paper's own benchmark-estimated boundary: ~September 2023** - notably
  earlier than OpenAI's declared date, per the paper's empirical testing.
- **The model's own self-reported cutoff when asked directly: September
  2021** - the paper flags this as unreliable, well earlier than either other
  figure.

**Still not treating any single one of these as settled fact.** "Not
confirmed" from the earlier table stands - what's changed is there's now a
citable, real academic source with three candidate numbers instead of zero,
which is more useful for a Limitations-section discussion of the genuine
uncertainty here than pretending a clean single date exists. If this becomes
load-bearing for the real contamination check, the responsible move is
probably to report a range (Sept 2021-July 2024) with this paper cited,
rather than pick one number, or to exclude this specific model from the
quantitative contamination sub-analysis and discuss it qualitatively instead
- a real methodology decision, not something to resolve by guessing.
