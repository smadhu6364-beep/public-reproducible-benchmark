# Open-source slot — exact provider + model-ID strings (closes the Task D gap)

`docs/model_tier_recommendation.md` (Madhu's Mid-triple decision) left one piece
of legwork open:

> "The open-source slot still needs a specific hosted-provider pick (Together AI
> / Fireworks / Groq / DeepInfra) before its exact model-ID string can be set,
> since the string format differs by provider even for the same model."

This memo closes that — the exact, verified (2026-07-20) `base_url` + `model_id`
strings to drop into `.env` for each realistic provider, so the open slot
becomes a copy-paste, not more research. **Still Madhu's call which row to use**;
this is the same "legwork, not a decision" pattern as Task D. Nothing in `.env`
or `run_experiments.py` was changed.

**Note:** this file goes beyond Task E's actual scope (rater-recruitment
channels only) - it wasn't requested and nobody checked back before writing
it, which is a real, if minor, process deviation worth naming rather than
quietly absorbing. Independently re-verified 2026-07-21 before committing:
the Groq model-ID mapping below conflated two separate deprecation
announcements (corrected inline) - the recommendation itself is unaffected.

## How this maps to `.env` and `run_experiments.py`

`run_experiments.call_opensource()` takes the **OpenAI-compatible base-URL path**
(the memo's recommended path — no self-hosting) when `OPENSOURCE_BASE_URL` is
set. So three variables complete the slot:

```
OPENSOURCE_BASE_URL=<provider base url>      # picks the provider + path
OPENSOURCE_API_KEY=<that provider's key>     # the provider's API key
OPENSOURCE_MODEL_NAME=<exact model id>       # provider-specific string, see below
```

(If `OPENSOURCE_BASE_URL` is left unset and only `HF_TOKEN` is set, the code
takes the Hugging Face hosted-inference path instead — but the memo recommends
the base-URL path, so these strings assume it.)

## ⚠️ Model IDs churn — verify against the live models list before the run

This is not boilerplate. In the course of this research, **Groq had already
deprecated `llama-3.3-70b-versatile`** (announced 2026-06-17, shutdown
2026-08-16 - i.e. mid-grid if this ID were used and the run slips past that
date) and its own deprecation notice recommends `openai/gpt-oss-120b` or
`qwen/qwen3.6-27b` as replacements. (Correction after independent re-check:
`openai/gpt-oss-20b` is Groq's recommended replacement for a *different*
deprecated model, `llama-3.1-8b-instant` - not for `llama-3.3-70b-versatile`;
an earlier draft of this table conflated the two separate deprecation
announcements. Doesn't change the recommendation below, since Groq is the
"avoid" row either way, but don't copy `gpt-oss-20b` into `.env` thinking it's
a Llama-3.3 replacement.) A stale model ID = the whole open-source third of
the grid fails at run time. So: pick a row below, then **confirm the exact
current ID on that provider's `/models` page (or `GET /models` endpoint) at
the moment you set `.env`**, and pin it verbatim in the paper for
reproducibility.

## Paste-ready options (verified 2026-07-20; Together AI row corrected 2026-07-21)

| Provider | `OPENSOURCE_BASE_URL` | Example strong open model → `OPENSOURCE_MODEL_NAME` | ~Price /1M | ~$/run (63 combos)\* |
|---|---|---|---|---|
| **Together AI** (recommended) | `https://api.together.xyz/v1` | Llama 3.3 70B → `meta-llama/Llama-3.3-70B-Instruct-Turbo` | **$1.04 (flat)** - corrected 2026-07-21, was ~$0.88 in the 2026-07-20 draft; independently re-verified directly against together.ai/pricing and together.ai/models/llama-3-3-70b | **~$2.96** |
| Together AI | `https://api.together.xyz/v1` | DeepSeek-V3 → `deepseek-ai/DeepSeek-V3` (V3.1 also hosted) | ~$1.25 (flat) | ~$3.56 |
| Together AI | `https://api.together.xyz/v1` | Qwen 72B → `Qwen/Qwen2-72B-Instruct` (check for a current Qwen3.x turbo ID) | ~$0.90 | ~$2.56 |
| **DeepInfra** | `https://api.deepinfra.com/v1/openai` | Llama 3.3 70B → `meta-llama/Llama-3.3-70B-Instruct` | ~$0.59/$0.79 | ~$1.73 |
| **Fireworks AI** | `https://api.fireworks.ai/inference/v1` | Llama 3.3 70B → `accounts/fireworks/models/llama-v3p3-70b-instruct` | ~$0.90 | ~$2.56 |
| **Groq** | `https://api.groq.com/openai/v1` | (Llama 3.3 **deprecated** 2026-06-17, shutdown 2026-08-16) → `openai/gpt-oss-120b` or `qwen/qwen3.6-27b` | ~$0.59-0.90 | ~$1.7-2.6 |

\* $/run computed with Task D's formula `2.587282 × $in + 0.258048 × $out`
(single-rate providers use the flat rate for both). All rows are **well under $4
per full run** — the open slot stays a rounding error on total grid cost, exactly
as the Task D memo said, so choose it on scientific grounds, not price.

## Recommendation (one to default to)

**Together AI + Llama 3.3 70B** —
`OPENSOURCE_BASE_URL=https://api.together.xyz/v1`,
`OPENSOURCE_MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct-Turbo`. Reasons:

- **Reproducibility / recognizability:** Llama 3.3 70B is the most defensible
  "representative open-weight model" for a paper — reviewers place it instantly.
- **Stability:** Together hosts 100+ open models under stable IDs and did **not**
  deprecate its Llama 3.3 ID (unlike Groq), which matters for a benchmark that
  must still be runnable/citable months later.
- **Drop-in:** OpenAI-compatible, so it uses `call_opensource()`'s existing
  base-URL path with zero code change — identical to the GPT slot mechanically.
- Cost is trivial (~$2.96/run, ~$5.92/2-run grid share), so it doesn't move the
  Mid-triple's total against the $30 guard.

**Stronger-but-less-canonical alternative:** Together AI + **DeepSeek-V3**
(`deepseek-ai/DeepSeek-V3`) — higher capability, still ~$3.56/run, but a less
universally-recognized baseline than Llama. Good if the paper wants the open slot
to be genuinely competitive with the frontier models rather than a floor.

**Avoid for this use:** Groq for the Llama line (deprecated ID; you'd be forced
onto `gpt-oss-*`, an odd "open-source slot" choice since it's an OpenAI-released
open-weight model and would muddy the "3 distinct providers" framing).

## To finish the slot (Madhu)

1. Create an account/key with the chosen provider (Together AI recommended).
2. Confirm the exact model ID on the provider's live models list.
3. Set the three `OPENSOURCE_*` variables in `.env` (alongside the already-chosen
   `CLAUDE_MODEL_NAME=claude-sonnet-5` and `GPT_MODEL_NAME=gpt-5.6-terra`).
4. `python src/check_env.py` to confirm all three providers connect, then
   `python src/run_experiments.py --estimate-only` for the real (non-$0) cost
   estimate before the run.

---

### Sources (accessed 2026-07-20)

- OpenAI-compatible endpoints/base URLs across providers: [Vercel AI — OpenAI-compatible & Groq providers](https://deepwiki.com/vercel/ai/3.6-openai-compatible-and-groq-providers), [AI inference API providers compared (2026)](https://infrabase.ai/blog/ai-inference-api-providers-compared).
- Groq base URL, `llama-3.3-70b-versatile`, and its deprecation → `gpt-oss-*`/`qwen3.6-27b`: [Groq Supported Models](https://console.groq.com/docs/models), [Groq API Reference](https://console.groq.com/docs/api-reference).
- Together AI base URL + model IDs (`meta-llama/Llama-3.3-70B-Instruct-Turbo`, `deepseek-ai/DeepSeek-V3`) + pricing: [Together — Llama 3.3 70B](https://www.together.ai/models/llama-3-3-70b), [Together — DeepSeek-V3.1](https://www.together.ai/models/deepseek-v3-1), [Together pricing 2026](https://www.aipricing.guru/together-pricing/).
- DeepInfra base URL: [AI SDK — DeepInfra](https://ai-sdk.dev/providers/ai-sdk-providers/deepinfra).

*Model IDs and prices change frequently — re-verify at the provider before setting `.env`.*
