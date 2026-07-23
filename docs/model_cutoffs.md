# Model training/knowledge cutoff dates (F6 research, 2026-07-21)

> **STALE as of 2026-07-23 - do NOT use these dates for a real contamination
> check.** The model tier researched below (Claude Sonnet 5, GPT-5.6 Terra,
> Llama 3.3 70B) was retired the same day this file was written about, for a
> budget-driven reason unrelated to these dates' accuracy - see CLAUDE.md's
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
That function deliberately does NOT hardcode any cutoff date in code (CLAUDE.md's
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
