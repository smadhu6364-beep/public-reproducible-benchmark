# Model-tier options for the experiment grid — a sourced shortlist (Task D)

**DECIDED 2026-07-20 (Madhu): the "Mid" triple** — Sonnet 5 (intro pricing)
+ GPT-5.6 Terra + a cheap open model (see the full table below; ~$21 for 2
runs with batch pricing, under CLAUDE.md's $30 guard, provided the run
happens before the Sonnet 5 intro rate ends 2026-08-31). The exact,
independently-verified API model ID strings for the Claude and GPT slots
are now pre-filled in `.env.example` (`claude-sonnet-5` and
`gpt-5.6-terra` — note OpenAI's bare `gpt-5.6` alias currently routes to
Sol, not Terra, so the explicit string matters). The open-source slot still
needs a specific hosted-provider pick (Together AI / Fireworks / Groq /
DeepInfra) before its exact model-ID string can be set, since the string
format differs by provider even for the same model.

**This was legwork, not a unilateral decision.** CLAUDE.md and the handoff
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

## Full-grid cost vs. CLAUDE.md's $30 cost guard

CLAUDE.md stops any full-grid run whose projected cost exceeds **$30** pending
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
  comparison and comes in at **~$21 for 2 runs with the batch discount** — under
  the guard — provided the grid runs **before the Sonnet 5 intro rate ends
  2026-08-31** and batch mode is used. This is the recommended target if a
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
