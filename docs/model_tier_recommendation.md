# Model-tier options for the experiment grid — a sourced shortlist (Task D)

**DECIDED 2026-07-20 (Madhu): the "Mid" triple** — Sonnet 5 (intro pricing)
+ GPT-5.6 Terra + a cheap open model. The exact, independently-verified API
model ID strings for the Claude and GPT slots are pre-filled in
`.env.example` (`claude-sonnet-5` and `gpt-5.6-terra` — note OpenAI's bare
`gpt-5.6` alias currently routes to Sol, not Terra, so the explicit string
matters). **UPDATE 2026-07-21 (Madhu): the open-source slot is now decided
too** — Llama 3.3 70B Turbo via Together AI (`docs/opensource_slot_options.md`
has the sourced provider comparison; `.env.example` has the exact
`OPENSOURCE_BASE_URL` / `OPENSOURCE_MODEL_NAME` / pricing strings pre-filled,
same pattern as Claude/GPT). All three model slots are fully specified; only
real API keys (all three) remain before a real run.

**CORRECTION 2026-07-21 — this memo's own cost table below is now stale for
the decided config, do not quote it.** The table's Mid-triple figures
(~$19.44/run, ~$38.89 at 2 runs, ~$31.19 batched) priced the open-source slot
against *DeepSeek Pro*, the option under consideration when this memo was
written - the slot was subsequently decided as *Llama 3.3 70B Turbo*
($1.04/$1.04, not DeepSeek Pro's assumed ~$1.34/run-implied rate) and the
Together AI pricing itself was independently corrected once already (see
`docs/opensource_slot_options.md`). The authoritative, independently-verified
numbers for the config actually in `.env.example` (re-derived twice: once by
hand, once by directly running `run_experiments.estimate_cost()` against the
real 189-cell grid, both 2026-07-21) are **$21.05/run, $42.11 at 2 runs,
$63.16 at 3 runs** - all of which exceed the $30 cost guard, a real
methodology-vs-guard tension not resolved at the time this memo was written;
see `results/preflight_report.md` and `docs/run_playbook.md` §5 for the full
picture and the options. This memo's own batch-pricing figure ($31.19) does
not reconcile with a real per-provider batch calculation either (~$24.02 for
2 runs if Claude+GPT are batched and the open-source slot is not) - treat the
batch figures here as illustrative of the *concept*, not as numbers to quote.

**This was legwork, not a unilateral decision.** PROJECT_SPEC.md and the handoff
were explicit that which paid model runs in each slot is Madhu's call; the
analysis below made that call fast from a sourced shortlist with real cost
estimates, and Madhu made it via a direct choice, not by default. **Nothing
in `.env` or `run_experiments.py` was changed by this memo itself** — the
pre-filled strings now in `.env.example` were added separately, after the
decision, as a direct consequence of it.

All pricing below was gathered from the web on **2026-07-20** and is dated and
sourced (pricing drifts — don't reuse a number here without re-checking). It is
consistent with the figures already hard-coded in `run_experiments.py`'s
`PRICING_PER_MTOK` (dated 2026-07-19); that table reads `$0.00` today only
because no model names are set, not because the grid is free.

---

## How the cost estimates were produced

Using `run_experiments.py`'s **own** token heuristic (`_chars_to_tokens`, ~4
chars/token) against the **real** rendered prompts for all 21 included projects
× 3 prompt strategies — i.e. the actual planning text each model would receive:

| Quantity | Value |
|---|---|
| Included projects | 21 |
| Prompt strategies | 3 (zero_shot, few_shot, structured) |
| Combos **per model, per run** (project × prompt) | 63 |
| **Input tokens per model per run** (sum of 63 rendered prompts) | **2,587,282** (~2.59 M) |
| Per-call input tokens | min 5,076 · avg 41,068 · max 81,855 |
| **Output tokens per model per run** (worst case: `DEFAULT_MAX_OUTPUT_TOKENS`=4096 × 63) | **258,048** (~0.26 M) |
| Full grid | 3 models × 3 prompts × 21 projects = **189 cells** |
| Total calls at 2 / 3 runs | 378 / 567 |

So for any model priced at `($in, $out)` per million tokens:

> **cost per model, per full run of its 63 combos = 2.587282 × $in + 0.258048 × $out**

**Caveats that make these estimates conservative (upper-bound-ish):**
- **Output is worst-cased.** Every call is billed as if it emitted the full
  4096-token cap; real risk registers are typically far shorter, so true output
  cost — and thus total cost for high-output-priced models — is likely well
  below these figures. Input dominates the total (2.59 M vs 0.26 M), so this
  matters most for the expensive-output frontier models.
- **Batch APIs cut frontier cost ~50%.** Anthropic and OpenAI both offer batch
  processing at roughly half price; a benchmark is not latency-sensitive, so
  this is a real, easy lever (modeled in the last table below).
- **Prompt caching** could cut input cost further (the identical planning doc is
  re-sent across a project's 3 prompts × runs), but the benefit is
  prompt-template-order-dependent and not modeled here — treat it as upside.
- The token heuristic is `run_experiments.py`'s own ~4 chars/token
  approximation, which that module itself flags as rough. Re-check against the
  provider console after the first small batch of real calls.

---

## Slot 1 — Claude (Anthropic)

Sourced 2026-07-20 (per-1M input / output):

| Model | Input | Output | $/run (63 combos) | 2 runs | 3 runs | Notes |
|---|---|---|---|---|---|---|
| **Claude Opus 4.8** | $5.00 | $25.00 | $19.39 | $38.78 | $58.16 | Flagship; strongest structured reasoning, priciest |
| **Claude Sonnet 5** | $2.00* | $10.00* | $7.76 | $15.51 | $23.27 | *Intro rate through **2026-08-31**, then $3/$15 (→ $11.63/run, $23.27 at 2 runs). Strong mid-tier |
| **Claude Haiku 4.5** | $1.00 | $5.00 | $3.88 | $7.76 | $11.63 | Cheapest/fastest; capability floor of the three |

**Tradeoffs:** Opus 4.8 gives the best-quality Claude result and the cleanest
"frontier" data point, but it is the single most expensive slot. Sonnet 5 is the
value pick **if the grid runs before 2026-08-31** (the intro rate nearly halves
it, and the Aug-2026 project deadline lines up with that window). Haiku is only
worth choosing if cost is the dominant constraint or if a deliberately
lower-tier Claude is wanted.

## Slot 2 — GPT (OpenAI)

The GPT-5.6 family launched 2026-07-09 (1.05 M context, 128 K max output).
Sourced 2026-07-20:

| Model | Input | Output | $/run (63 combos) | 2 runs | 3 runs | Notes |
|---|---|---|---|---|---|---|
| **GPT-5.6 Sol** | $5.00 | $30.00 | $20.68 | $41.36 | $62.03 | Flagship; peer to Opus 4.8, most expensive GPT |
| **GPT-5.6 Terra** | $2.50 | $15.00 | $10.34 | $20.68 | $31.02 | Mid-tier; the natural peer to Sonnet 5 std |
| **GPT-5.6 Luna** | $1.00 | $6.00 | $4.14 | $8.27 | $12.41 | Cheapest 5.6; peer to Haiku 4.5 |

(`GPT-5.4` at $2.50/$15.00 is an older equivalent to Terra if a more-established
model is preferred over the two-week-old 5.6 line.)

**Tradeoffs:** same shape as the Claude slot — Sol for the strongest result at
frontier cost, Terra for a balanced mid-tier, Luna for budget. Terra pairs
naturally with Sonnet-5-standard for a like-for-like mid-tier cross-provider
comparison.

## Slot 3 — Open-source (open-weight)

**Recommended access path: a hosted, OpenAI-compatible endpoint** (Together AI,
Fireworks AI, Groq, or DeepInfra) via `run_experiments.py`'s existing
`OPENSOURCE_BASE_URL` path — **not** self-hosting, and marginally preferred over
the `HF_TOKEN` path. Reasoning:

- **No self-hosting.** The repo documents no GPU infrastructure anywhere.
  Standing up a GPU (rented or owned) to serve ~130–190 calls means idle
  hardware cost, ops overhead, and an extra reproducibility burden (documenting
  exact hardware/quantization) — not worth it at this volume when hosted
  per-token inference costs **under $2 per full run** (see table).
- **OpenAI-compatible base URL** means the call path is byte-for-byte the same
  as the GPT slot (`run_experiments.call_opensource` already handles it), so
  it's the lowest-risk integration.
- **vs the `HF_TOKEN` path:** HF Inference Providers works and routes to these
  same providers, but pointing `OPENSOURCE_BASE_URL` directly at one provider
  gives clearer per-model pricing and simpler debugging. Either is fine; the
  direct endpoint is simpler.

Candidate open-weight models (hosted pricing, sourced 2026-07-20):

| Model | Input | Output | $/run (63 combos) | 2 runs | 3 runs | Notes |
|---|---|---|---|---|---|---|
| **DeepSeek V4 Flash** | $0.14 | $0.28 | $0.43 | $0.87 | $1.30 | Cheapest strong option; negligible cost |
| **Llama 3.3 70B** (Groq) | $0.59 | $0.79 | $1.73 | $3.46 | $5.19 | Most-recognized open baseline — good for citation/reproducibility |
| **DeepSeek V4 Pro** | $0.435 | $0.87 | $1.35 | $2.70 | $4.05 | Higher-capability DeepSeek; still cheap |
| **Qwen3.x** (~$0.15–0.23 in) | ~$0.20 | ~$0.60 | ~$0.67 | ~$1.34 | ~$2.01 | Strong at structured/JSON output; very cheap |

**Tradeoffs:** the open slot is a rounding error on total cost, so choose it on
**scientific** grounds, not price. **Llama 3.3 70B** is the most defensible
"representative open-weight model" for a paper (widely recognized, easy for
reviewers to place). **DeepSeek V4** (Flash or Pro) is stronger and cheaper but
less of a household baseline. **Qwen** is a strong middle ground and notably
good at emitting schema-valid JSON, which matters for `parse_model_response`'s
success rate. Whichever is chosen, pin the exact model string and provider for
reproducibility (open-weight models are re-hosted at varying quantizations).

---

## Full-grid cost vs. PROJECT_SPEC.md's $30 cost guard

PROJECT_SPEC.md stops any full-grid run whose projected cost exceeds **$30** pending
confirmation. Total grid cost = (Claude slot + GPT slot + open slot) × runs.
Representative triples:

| Triple (Claude + GPT + open) | 1 run | **2 runs** | 3 runs | vs $30 guard (2 runs) |
|---|---|---|---|---|
| **Budget** — Haiku 4.5 + GPT-5.6 Luna + DeepSeek V4 Flash | $8.45 | **$16.90** | $25.34 | ✅ clears, even at 3 runs |
| **Low-mid** — Haiku 4.5 + GPT-5.6 Terra + Llama 70B | $15.95 | **$31.89** | $47.84 | ⚠️ just over |
| **Mid** — Sonnet 5 (intro) + GPT-5.6 Terra + DeepSeek Pro | $19.44 | **$38.89** | $58.33 | ❌ over |
| **Mid-std** — Sonnet 5 (std) + GPT-5.6 Terra + Llama 70B | $23.70 | **$47.40** | $71.11 | ❌ over |
| **Flagship** — Opus 4.8 + GPT-5.6 Sol + Kimi K2.6 | $43.56 | **$87.11** | $130.67 | ❌ well over |

**With the 50% Batch API discount** applied to the two frontier slots (open slot
unchanged — already trivial), the picture changes materially:

| Triple | batch, 2 runs | batch, 3 runs |
|---|---|---|
| Budget | $8.88 | $13.32 |
| Low-mid | $17.68 | $26.52 |
| **Mid** (Sonnet 5 intro + Terra + DeepSeek Pro) | **$20.79** | $31.19 |
| Mid-std | $25.43 | $38.15 |
| Flagship | $47.05 | $70.57 |

---

## Bottom line for the decision (Madhu still makes it)

- **If staying strictly under $30 without batch:** the **Budget** triple (Haiku
  4.5 / GPT-5.6 Luna / DeepSeek V4 Flash) is the only one that clears the guard
  at 2–3 runs. It answers RQ2 across three genuinely different providers but at
  each provider's capability floor.
- **Best quality-for-budget:** the **Mid** triple (Sonnet 5 at its intro rate /
  GPT-5.6 Terra / a cheap open model) is the strongest like-for-like mid-tier
  comparison. **Corrected 2026-07-21** (this line previously said "~$21 for 2
  runs with the batch discount," conflating the ~$21/run SYNCHRONOUS figure
  with a batched 2-run total): for the actually-decided open-source slot
  (Llama 3.3 70B Turbo, not this table's DeepSeek Pro placeholder), the real
  batched cost is **~$21.05/run synchronous, ~$24.02 for 2 runs batched**
  (claude+gpt batched, opensource stays synchronous — see the correction note
  at the top of this file and `results/preflight_report.md`) — still under the
  guard, provided the grid runs **before the Sonnet 5 intro rate ends
  2026-08-31** and `--batch` is used. This is the recommended target if a
  mid-tier result is wanted.
- **Flagship (Opus 4.8 / GPT-5.6 Sol / strong open):** the strongest possible
  result, but ~$87 at 2 runs (~$47 with batch) — needs an explicit
  `--confirm-cost` and a decision to exceed the $30 guard.
- **Design note (not just cost):** keep the three slots at *comparable
  capability tiers* (all mid, or all flagship). Mixing a flagship Claude with a
  budget GPT would confound "provider" with "tier" and muddy the RQ2 comparison.

**To act on any choice:** set the three model strings in `.env`, then run
`python src/run_experiments.py --estimate-only` to get the tool's own
confirmation of the cost before the real run. (That command prints `$0.00` today
only because the names are unset.) Consider adding `batch` mode and re-checking
output-token assumptions after the first few real calls.

---

### Sources (all accessed 2026-07-20)

- Anthropic pricing: [platform.claude.com/docs — Pricing](https://platform.claude.com/docs/en/about-claude/pricing); corroborated by [TLDL Anthropic pricing (July 2026)](https://www.tldl.io/resources/anthropic-api-pricing) and [BenchLM Claude API pricing](https://benchlm.ai/anthropic/api-pricing).
- OpenAI pricing: [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing); corroborated by [AI Pricing Guru — OpenAI (GPT-5.6)](https://www.aipricing.guru/openai-pricing/) and [TLDL OpenAI pricing (July 2026)](https://www.tldl.io/resources/openai-api-pricing).
- Open-weight hosted pricing: [Inference.net LLM pricing comparison](https://inference.net/content/llm-api-pricing-comparison/), [AI Pricing Guru — Groq](https://www.aipricing.guru/groq-pricing/), [AI Pricing Guru — Together](https://www.aipricing.guru/together-pricing/), [DeepInfra — Qwen pricing 2026](https://deepinfra.com/blog/qwen-api-pricing-2026-guide), [pricepertoken.com](https://pricepertoken.com/).

*Pricing changes frequently; every figure here is dated 2026-07-20 and should be
re-verified at the source before a real run.*

---

## ADDENDUM 2026-07-23 (Madhu, budget-driven): the paid triple above was replaced

Everything above this line is historical record, not the live decision -
kept for transparency about how the original choice was reached, not deleted
or silently rewritten.

**What happened:** on the first real attempt to spend against all three
decided accounts (Anthropic, OpenAI, Together AI - all three keys
independently verified reachable via `check_env.py` beforehand), every
single one rejected the actual spend-incurring call:
- Anthropic: `400 - Your credit balance is too low to access the Anthropic API`
- OpenAI: `429 - insufficient_quota, you exceeded your current quota`
- Together AI: `402 - Credit limit exceeded`

None of the three accounts had funded billing. Faced with a real budget
constraint, Madhu chose to redesign the model lineup around genuinely
free-tier providers rather than pay - see PROJECT_SPEC.md's RQ2 correction note
for why this is a real, disclosed change to the comparison's shape, not a
relabeling.

**The new lineup**, researched via live web search on 2026-07-23 (not
assumed from training knowledge - free-tier terms and model IDs both churn
quickly, same discipline this file already used for pricing):

| Slot | Provider | Model | Free-tier limit (as researched 2026-07-23) |
| --- | --- | --- | --- |
| `claude` (kept as MODEL_DISPATCH's role label) | Google Gemini, via its documented OpenAI-compatible endpoint | `gemini-2.5-flash` | 1,500 requests/day, no credit card |
| `gpt` | Groq | `openai/gpt-oss-120b` (OpenAI's own open-weight model family, served by a third party) | shares Groq's free pool |
| `opensource` | Groq | `qwen/qwen3.6-27b` | 14,400 requests/day org-wide, 30 requests/min, no credit card |

Grid math: 378 total calls (189 cells x 2 runs), ~252 of them on Groq (well
under its 14,400/day budget) and ~126 on Gemini (well under its 1,500/day
budget) - comfortably fits in under a day, genuinely $0.

**Real, disclosed consequences of this change, not smoothed over:**
- RQ2's comparison shape changed from 2 proprietary + 1 open-weight to 1
  proprietary + 2 open-weight. State this explicitly in the paper.
- `--batch`/`--batch-check` (src/run_experiments.py) are now inapplicable -
  they submit to Anthropic's and OpenAI's own native batch APIs specifically,
  which the Gemini/Groq OpenAI-compatible endpoints were never verified to
  support, and there is no cost discount left to batch for anyway. The batch
  code path is left in place, untouched, not deleted - see that file's module
  docstring.
- `docs/model_cutoffs.md`'s researched training-cutoff dates are for the
  RETIRED paid triple (Claude Sonnet 5, GPT-5.6 Terra, Llama 3.3 70B) and do
  NOT apply to the new 3 models - that file is flagged as needing
  re-research, not silently reused, before the opt-in pretraining-
  contamination check (`metrics.pretraining_cutoff_report()`) is ever run
  against real data from the new lineup.
- `docs/opensource_slot_options.md` (the research that originally chose
  Together AI/Llama) is now superseded for the `opensource` slot's provider
  choice, though its comparison methodology may still be useful reference.

**Not resolved here:** the Gemini free tier is documented (by third-party
sources, not Google's own pricing page directly) to have a "billing trap" -
enabling billing on the same Google Cloud project for any other reason can
silently move it off the free tier. Whoever sets up `GEMINI_API_KEY` should
use a clean, billing-free Google account and re-verify this before a real
run, not assume the third-party sources are exactly right.

## ADDENDUM 2026-07-23 (later the same day): Groq's free tier is structurally too small - moved `gpt`/`opensource` to SambaNova Cloud

The lineup above was never real-call-verified before this addendum - only
`check_env.py`'s cheap `/models` reachability check had run. The first actual
scoped smoke test (1 project x 3 models x 3 prompts, 9 real calls) surfaced a
real, structural problem, not a flaky one:

- **Gemini**: `gemini-2.5-flash` returned `404 - no longer available to new
  users` (still listed in the catalog, but new accounts are blocked). Fixed
  same-day - `gemini-flash-latest` verified working; already applied to
  `.env`/`.env.example`. Does not affect this addendum's subject (Groq).
- **Groq**: both `openai/gpt-oss-120b` and `qwen/qwen3.6-27b` returned
  `413 - Request too large ... TPM Limit 8000` - real prompts run ~30-34K
  tokens (full planning documents in context), ~4x over. Independently
  confirmed against `console.groq.com/docs/rate-limits` directly (not an
  aggregator): **8K TPM for both models chosen here**, and even Groq's other
  free models cap at 12K TPM (`llama-3.3-70b-versatile`) - staying within
  Groq's free catalog does not fix this. This is a hard per-request ceiling,
  not a pacing/rate problem - retry/backoff cannot help.

**Two alternatives were researched and compared, primary sources only:**

- **Cerebras** - rejected on two independent grounds: their own docs
  (`inference-docs.cerebras.ai/support/rate-limits`) require a verified
  payment method before API access activates at all (not the "genuinely no
  card" free tier several aggregators claimed), and even setting that aside,
  `gpt-oss-120b`'s Free Trial limit is 30K TPM - barely above Groq's wall,
  still likely under this project's real per-call token count.
- **OpenRouter** - a genuinely free, no-card `:free`-suffix tier exists
  (confirmed directly via `openrouter.ai/docs/api-reference/limits`: 20
  RPM, 50-1000 RPD, **no TPM/per-request cap at all** - the opposite
  problem from Groq), and `openai/gpt-oss-120b:free` (131K context) is
  real and available there. Not chosen as the primary fix: (a) OpenRouter's
  own privacy docs describe free-model routing going to whichever backend
  is cheapest/least-loaded at request time, a real reliability/consistency
  risk for a benchmark study that cares about stable model behavior across
  runs, and (b) the `qwen/qwen3.6-27b` model isn't offered free there,
  which would have required a further Qwen-tier substitution
  (`qwen/qwen3.6-plus:free`) on top of the provider change.
- **SambaNova Cloud (chosen)** - checked directly against
  `docs.sambanova.ai/docs/en/models/rate-limits` and
  `.../models/sambacloud-models`: genuinely card-optional free tier ("Free
  Tier: Applied when there is no payment method linked with your account"),
  **both `openai/gpt-oss-120b` (same exact model, no further RQ2 disclosure
  needed) and `Meta-Llama-3.3-70B-Instruct` (this project's ORIGINAL
  pre-redesign open-source pick, before any of today's churn) are already on
  the free tier**, both at 128K context, and the free-tier rate-limit table
  has **no TPM row at all** - only RPM (20), RPD (20), and TPD (200,000
  tokens/day) per model, none of which reject a single ~30-34K-token request
  outright the way Groq's TPM wall did.

**Real-call verified before wiring this in, not just trusted from the docs
page** (the exact discipline that caught the Gemini 404 and the Groq wall in
the first place): sent the actual `zero_shot.txt` template rendered against
`P-UK-HyNetCCUSCluster`'s real processed text (~28,400 prompt tokens per
SambaNova's own `usage` field) to both models.

- `Meta-Llama-3.3-70B-Instruct`: succeeded cleanly, `finish_reason="stop"`,
  real risk-register-shaped JSON content, even at a small `max_tokens`.
- `openai/gpt-oss-120b`: at `max_tokens=1024`, returned EMPTY content with
  `finish_reason="length"` - this model spends hidden reasoning tokens out
  of the `max_tokens` budget before any visible output, the same class of
  behavior already found for Gemini's "thinking tokens". At
  `max_tokens=4096` (this project's `DEFAULT_MAX_OUTPUT_TOKENS`), it
  succeeded cleanly (`completion_tokens=3475`, `finish_reason="stop"`, real
  content).

**Not resolved, and worth tracking during the real run:** SambaNova's
responses expose no rate-limit-related headers at all (checked directly -
only `date`/`content-type`/`inference-id`/`x-request-id`/HSTS, nothing
`ratelimit`-shaped), so whether the documented 200,000 TPD/model budget is
genuinely independent per model or shared account-wide cannot be confirmed
without a real multi-day run. Docs-page arithmetic (200,000 TPD / ~33,000
tokens-per-call ≈ 6 calls/day/model; 126 calls needed per model at 2 runs x
21 projects x 3 prompts ⇒ ~21 days to clear one model's grid, assuming
independent budgets) is a real planning input, not a confirmed fact - "looks
fine on the docs page" has now been wrong twice today (Gemini, Groq) before
this addendum even started. Treat the ~21-day estimate as a risk to watch
against the Aug-2026 deadline, not a solved timeline.

Updated: `run_experiments.py` (`GEMINI_BASE_URL`/`SAMBANOVA_BASE_URL`,
`call_gpt`/`call_opensource`, `PRICING_PER_MTOK`), `check_env.py`
(`check_gpt_slot`/`check_opensource_slot`), `.env`/`.env.example`
(`SAMBANOVA_API_KEY` replaces `GROQ_API_KEY`; `OPENSOURCE_MODEL_NAME` reverts
to `Meta-Llama-3.3-70B-Instruct`), `PROJECT_SPEC.md`'s RQ2 note, and this file.

## ADDENDUM 2026-07-23 (later the same day): the real full-grid attempt confirms the ~21-day estimate, and reveals Gemini has the same problem

Ran the real 189-cell x 2-run grid (378 calls) for the first time, rather
than continuing to estimate from docs pages. Result: **13 succeeded, 365
failed** in one pass - both providers hit hard daily quotas almost
immediately, confirming this is a real structural wall, not the "~21 days,
assuming independent budgets" hedge above.

- **Gemini's real free-tier daily cap is 20 requests/day**, not the
  1,500/day this file's original table cited - that number was wrong for
  the model actually in use (`gemini-flash-latest`, which the real 429
  error identifies as currently resolving to `gemini-3.6-flash`; the
  1,500/day figure was likely researched against an older Gemini
  generation and never re-verified against this specific model). 11 of the
  63 needed Gemini cells cleared before the daily quota was exhausted.
- **SambaNova's 200,000 TPD budget is confirmed independent per model** -
  `gpt` and `opensource` reported different `Current usage` figures at the
  same moment, resolving the "shared vs. independent" question in the
  addendum above in the favorable direction. Only 1 `gpt` and 1
  `opensource` cell cleared today, but this is an undercount: this same
  session's own earlier real-call verification (confirming the SambaNova
  fix worked, diagnosing the `max_tokens` truncation bug) already spent
  most of today's 200K/model budget before the full-grid attempt started.
  A day without that prior testing should clear closer to the ~6-7
  calls/model/day the TPD arithmetic predicts.
- **Real projected timeline: ~3 weeks of daily re-runs**, bounded by
  SambaNova (126 calls needed per model at ~6-7/day) rather than Gemini (63
  calls needed at ~11-20/day, clears in under a week). Madhu's explicit
  decision (2026-07-23): accept this timeline - re-run
  `python src/run_experiments.py --runs 2` once daily; append-only raw
  outputs and `next_free_run_index` make this safe to just repeat without
  any special resume logic.
