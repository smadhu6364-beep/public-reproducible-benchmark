# Run playbook — the full experiment, end to end

The ordered command sequence for producing the paper's results, with the flags
that matter and the traps that have actually bitten this project. Written
2026-07-21; every command below was run (or `--help`-verified) against the repo
as it stands, so the flags are real, not remembered.

Read `PROJECT_SPEC.md` first for the frozen research questions and methodology rules.
This document is *how*, not *what* or *why*.

---

## 0. Environment — use the venv, not bare `python`

```bash
python -m venv .venv && .venv/Scripts/activate    # Windows; use bin/activate on POSIX
pip install -r requirements.txt
```

**This is not boilerplate.** The bare `python` on PATH in this workspace has
`numpy` and `jsonschema` but **not `matplotlib`** — so steps 1-8 appear to work
and then step 9 dies with `ModuleNotFoundError: No module named 'matplotlib'`.
If you skipped activation, `.venv/Scripts/python.exe` works as a direct path.

Everything below assumes `python` means the venv's python.

## 1. Keys

```bash
cp .env.example .env      # then fill in the two keys
python src/check_env.py   # verifies each provider actually answers
```

**REDESIGNED 2026-07-23 (Madhu, budget-driven), then REDESIGNED AGAIN
2026-07-23 (later the same day):** the originally-decided paid triple
(`claude-sonnet-5` / `gpt-5.6-terra` / Llama 3.3 70B Turbo via Together AI)
all hit real billing/quota errors on the first actual spend attempt, so the
lineup moved to Gemini + Groq. Groq's free tier then turned out to have a
hard 8,000 TPM per-request cap that this project's real ~30-34K-token
prompts exceed ~4x — a real smoke test confirmed this outright, not a
pacing issue — so the `gpt`/`opensource` slots moved again, to SambaNova
Cloud. See PROJECT_SPEC.md's RQ2 correction note and
`docs/model_tier_recommendation.md`'s dated addenda for the full history.
`.env.example` is now pre-filled with 3 genuinely free-tier models across
just **2 real accounts**: Google Gemini (`GEMINI_API_KEY`, from
[aistudio.google.com/apikey](https://aistudio.google.com/apikey)) and
SambaNova Cloud (`SAMBANOVA_API_KEY`, from
[cloud.sambanova.ai](https://cloud.sambanova.ai), shared by both the `gpt`
and `opensource` slots). Neither requires a credit card as of this writing.

`check_env.py` reports per-slot `CONFIGURED` / `RESULT` (3 rows: Gemini,
SambaNova×2). Do not proceed to step 6 until all three say configured and
reachable — while every slot is free now, a systemic key failure mid-grid
still wastes time re-running the affected cells.

## 2. Corpus extraction (only if `data/raw/` changed)

```bash
python src/extract.py --all
```

Rebuilds `data/processed/*.txt` from `data/raw/` PDFs, excising the risk-register
pages recorded in `corpus_manifest.csv` into `data/risk_source_audit/`.

`data/processed/` is already complete and committed, so **you normally skip
this.** Only rerun if a PDF or a manifest page range changed. Note it produces
**22** files against 21 included projects — `P-REGION-AIM4Learning` is processed
but set aside; that is expected, and the grid excludes it by reading the
manifest rather than globbing the directory.

## 3. Leakage audit — do not skip this after any step-2 rerun

```bash
python src/audit_corpus.py
```

Writes `results/corpus_audit_report.md`. This is the check that the human risk
register really was excised from the text models will see. Current expected
state: **19 PASS / 1 WARN / 1 FAIL**, where the 1 FAIL (`P-MAR-...`) and 1 WARN
(`P-UK-PadeswoodCCUS`) are both documented false positives — see
`results/corpus_audit_review_notes.md` before treating either as a real leak.
Any *new* FAIL is a genuine stop-the-line event.

> **One check is network-dependent and will vary by environment.**
> `P-UK-FreeBreakfastClubs` has no PDF, so its Check 1 is replaced by a live
> re-fetch of the real gov.uk publication (`audit_free_breakfast_clubs_html`).
> Re-running this in a network-restricted environment (confirmed 2026-07-21: a
> sandboxed re-run here got `Tunnel connection failed: 403 Forbidden` on that
> one URL, nothing else) turns its status from PASS to WARN and the summary
> line from 19/1/1 to 18/2/1. **That is a reachability artifact of the runner,
> not a corpus finding** — every other project's page-range and leak-check
> result reproduced byte-for-byte identically in that same run. If you see this
> specific WARN with this specific error text, don't treat it as a new leak;
> re-run somewhere with unrestricted outbound access before concluding
> anything changed.

## 4. Matching threshold (already settled — informational)

```bash
python src/validate_threshold.py
```

The threshold is **0.45**, validated against a hand-labeled pair set and
justified in `src/match.py`'s docstring + `results/threshold_validation_report.md`.
Rerun only if the embedding model changes. `match.py` is the single source of
truth for the value.

## 5. Cost estimate — always, before running

```bash
python src/run_experiments.py --estimate-only --runs 2
```

Prints per-model and total projected cost, makes **no API calls**.
**REDESIGNED 2026-07-23 (Madhu, budget-driven):** the originally-decided paid
triple all hit real billing/quota errors on the first actual spend attempt
(see `docs/model_tier_recommendation.md`'s dated addendum) and was replaced
with 3 genuinely free-tier models. The estimate is now, correctly,
**`estimated_total_usd: 0.0`** — verified directly, not assumed. PROJECT_SPEC.md's
$30 cost guard and `--confirm-cost` are effectively moot for this lineup
(nothing will ever exceed $30), but both remain in the code as a safeguard
if a future funded run reverts to paid providers.

## 6. The grid

```bash
python src/run_experiments.py --runs 2
```

One synchronous call per (project, model, prompt, run) cell — no `--batch`,
no `--confirm-cost` needed. **`--batch`/`--batch-check` are now
INAPPLICABLE, not just unnecessary:** they submit to Anthropic's and
OpenAI's own native batch APIs specifically, which none of
Gemini/Groq/SambaNova's OpenAI-compatible endpoints are wired for, and
there's no cost discount left to batch for anyway since every slot is free.
Passing `--batch` against the current `.env` will fail (it still requires
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, which the free-tier `.env.example` no
longer sets by default) — see `run_experiments.py`'s module docstring if a
funded run ever needs to revive that path.

- `--temperature` defaults to 0.1 and is hard-limited to [0, 0.2] per PROJECT_SPEC.md.
- Raw outputs are **append-only**: `next_free_run_index` picks the lowest unused
  index, and `run_one` refuses to overwrite an existing file. Re-invoking adds
  runs rather than clobbering them — which also means a partial grid is safe to
  resume by just running the command again.
- Scope it down while smoke-testing: `--project P-SRB-CompetitivenessJobs
  --model claude --prompt zero_shot --runs 1` is one call, genuinely free.
- Exit codes: `2` = every call failed (systemic — bad keys/network, treat as "no
  run happened"); `3` = some failed; `1` = cost guard (should not fire at $0.00).
- **REAL FULL-GRID ATTEMPT 2026-07-23 confirmed both providers hit hard
  daily quotas fast.** Ran the actual 378-call grid: 13 succeeded, 365
  failed, in one pass. SambaNova's 200,000 TPD budget IS confirmed
  independent per model (`gpt` and `opensource` showed different `Current
  usage` figures at the same moment) - real ~6-7 calls/model/day at this
  project's ~30-34K-token prompt size, so **~21 days** to clear one model's
  126-call share. **Gemini's real limit is 20 requests/day, NOT 1,500/day**
  - that figure was wrong for `gemini-flash-latest` (confirmed via the real
    429 error body, which names the resolved model `gemini-3.6-flash` and
    states `quotaValue: '20'`); Gemini clears its 63-call share in under a
  week at that rate. **Real projected timeline for the full grid: ~3 weeks
  of daily re-runs**, bounded by SambaNova. Madhu's decision (2026-07-23):
  accept this timeline rather than cut runs or pay - just re-run
  `python src/run_experiments.py --runs 2` once a day; append-only raw
  outputs make repeating the exact same command safe every time.

Every run — batched or synchronous — appends `model_version`, `run_date`,
`temperature`, `temperature_applied`, `prompt_sha256` to
`results/run_config.jsonl`. That file is the reproducibility record — do not
delete it.

## 7. Method A — semantic matching and metrics

```bash
python src/match.py --all                                   # -> results/scored/*.match.json
python src/metrics.py --scored-dir results/scored --out results/metrics.json
```

`metrics.py` prints to stdout unless `--out` is given; **pass `--out`**, because
step 9 consumes that JSON.

The report contains RQ1/RQ2/RQ3 aggregates *and* the both-ways variants added
after the 2026-07-21 scoping decisions (`*_corpus_wide_only`,
`by_category_excluding_parse_failures`). `results/metrics_review_findings.md`
explains what each answers — read it before quoting a number in the paper, since
the default keys and the variants deliberately cover different document sets.

## 8. Method C — LLM-as-judge (supplementary only)

```bash
python src/judge.py --all
```

Supplementary evidence per PROJECT_SPEC.md — never a headline result. The judge never
sees the ground-truth register.

## 9. Figures

```bash
python analysis/make_figures.py --metrics results/metrics.json
```

Writes RQ1/RQ2/RQ3 figures to `analysis/figures/`. Use `--note` to stamp a
caption on every figure — mandatory when plotting anything that isn't the real
final data:

```bash
python analysis/make_figures.py --metrics scratch/synthetic_metrics.json \
    --note "SYNTHETIC DATA - pipeline validation only"
```

`analysis/gen_synthetic_scored.py` fabricates `*.match.json` fixtures for
exercising steps 7-9 without any model spend. Its output is scratch-only and
gitignored — **never** let synthetic files reach `results/scored/`.

## 10. Method B — rater packets (needs step 6 output)

```bash
python src/build_rater_packets.py --min-uk-per-cell 1 --raters 4
```

- `--min-uk-per-cell 1` is the **decided** setting (Madhu, 2026-07-20): without
  it a naive draw can leave entire model×prompt cells with no UK register.
- `--seed` (default 20260720) makes the whole sample reproducible; it is recorded
  in `sampling_summary.json`.
- Produces `results/rater_packets/`: `blinding_map.csv` (**GITIGNORED — the
  de-anonymizing key, never send this to a rater**), `rater_assignments/*.csv`
  and `packets/*.md` (both shareable, opaque `REG-###` codes only).
- Safe to run before the grid exists: sampling/blinding/assignment complete, and
  packets report as `pending_generation` instead of failing. Re-run after step 6
  to fill in the packet bodies.

Rater recruitment is the real bottleneck here, not the code — see
`docs/rater_recruitment_channels.md` and `docs/rater_protocol.md`.

## 11. Method B — kappa (needs completed rater sheets back)

```bash
python src/compute_kappa.py --out results/kappa_report.json
```

- Reads completed sheets from `results/rater_packets/rater_assignments/`
  (a rater's returned, filled-in CSV is expected to land back in that same
  directory) plus `blinding_map.csv`, and requires every rater to have
  scored every sampled register (the full-overlap design, section 3.1 of
  `docs/rater_protocol.md`) — fails loudly, naming the specific rater/code,
  if a sheet is incomplete rather than silently computing over a partial
  set.
- Reports Fleiss' kappa **and** mean Likert score per dimension
  (Completeness, Accuracy, Actionability), overall / by-model / by-prompt.
- `analysis/gen_synthetic_kappa_demo.py` shows the report's shape with
  fabricated scores before real ratings exist — same synthetic-fixture
  convention as step 9's `gen_synthetic_scored.py`, output gitignored under
  `scratch/`.
- Not yet exercised against real rater data (no ratings exist yet) — same
  caveat as `--batch`'s "confirmed against real SDK shapes, not a live call"
  note in section 6a. Spot-check the first real kappa run by hand.

## Tests

```bash
python -m unittest discover -s tests
```

438 tests, ~14s, **no network, no API keys, no spend** — the embedding model,
the PDF reader, and all three providers (sync AND batch) are stubbed. One
test (a real-embedding-model end-to-end check in `test_validate_threshold.py`)
is skipped by default; opt in with `RUN_SLOW_TESTS=1` if you need it. Run
this before and after touching anything in `src/`. Coverage is concentrated
where this project has actually had bugs or where a silent failure would
invalidate results:

| File | Protects |
| --- | --- |
| `test_extract.py` | manifest page-range parsing (source of the Serbia/Uganda bugs) |
| `test_extract_excision.py` | the excision partition itself — every page in exactly one output, 1-indexing, leakage guards |
| `test_extract_driver.py` | the `--all` orchestration layer — one project failing doesn't stop the rest, unexpected exceptions aren't swallowed |
| `test_audit_corpus.py` | the leakage auditor's **false-negative** surface + a real-corpus regression |
| `test_audit_corpus_driver.py` | the FAIL-beats-WARN-beats-PASS verdict aggregation, the HTML-only special case, CLI exit codes |
| `test_match.py` | greedy one-to-one matching, threshold boundary |
| `test_match_driver.py` | `score_raw_output`'s parse-failed handling + the `--all`/`--file` CLI |
| `test_validate_threshold.py` | the sweep/recommend/Youden's-J statistics behind the 0.45 threshold decision |
| `test_metrics.py` | recall/precision guards, subgroup separation, scoping variants, the opt-in pretraining-cutoff contamination check |
| `test_parsing.py` | model + judge response parsing, incl. the bool-as-int regression |
| `test_judge_driver.py` | `judge.py`'s CLI/driver layer |
| `test_rater_packets.py` | sampling determinism, UK stratification, **blinding integrity**, CLI (`main()`) |
| `test_run_pipeline.py` | append-only, reproducibility fields, leakage guard, cost estimator |
| `test_batch.py` | batch request/response shapes vs. real SDK contracts, submit/collect against `_finalize_run`, batch cost discount |
| `test_figures.py` | figure rendering + the metrics.json ↔ make_figures key contract |
| `test_show_path_helper.py` | the out-of-repo relative-path crash fix, across all 5 files it was applied to |
| `test_check_env.py` | `check_env.py`'s pre-spend connectivity checks |
| `test_env_example.py` | `.env.example` stays in sync with what the code actually reads |
| `test_gitignore_leakage.py` | leakage-sensitive paths stay gitignored (and aren't already tracked via `git add -f`) |
| `test_ground_truth_data.py` | all 21 ground-truth files conform to `ground_truth_schema.json` |
| `test_requirements_consistency.py` | `requirements.txt` vs. actual imports in `src/`/`analysis/`, both directions |
| `test_spec_compliance.py` | category enum + 1-5 scales + repo-structure directories match PROJECT_SPEC.md's own text |
| `test_playbook_smoke.py` | the full `run_experiments.py`->`match.py`->`metrics.py`->`make_figures.py` chain, one shared sandbox |
| `test_compute_kappa.py` | Fleiss' kappa formula (vs. an independently hand-derived example), CSV validation, full-overlap design, CLI |
| `test_gen_synthetic_kappa_demo.py` | the kappa synthetic demo runs the real `compute_report()`, output is clearly labeled |

`test_figures.py` needs matplotlib and **skips** (does not fail) on an
interpreter without it — so `python -m unittest discover -s tests` is green
either way, which is also why §0's venv warning matters.

## Things that will bite you

1. **Bare `python` lacks matplotlib.** Activate the venv (§0).
2. **`--batch`/`--batch-check` are retired for the current setup** (§6) — they
   still work only against paid Anthropic/OpenAI accounts, which `.env.example`
   no longer configures by default. Use the plain synchronous path.
3. **`.env` does not exist until you `cp .env.example .env`** — nothing in
   steps 6/8 can run until it does, and until `GEMINI_API_KEY`/`SAMBANOVA_API_KEY`
   are filled in.
4. **Raw outputs are append-only.** If you want a clean re-run you must move the
   old files aside deliberately; nothing overwrites them for you.
5. **Model IDs and free-tier terms both churn fast for Gemini/SambaNova** —
   the exact strings in `.env.example` were correct as of 2026-07-23.
   Re-confirm both providers' live model lists before a real run if more
   than a few weeks have passed (same discipline this project already
   applied to Together AI's model ID, which got deprecated once already;
   Groq's free tier was ruled out entirely mid-project when its 8K TPM
   per-request cap turned out too small for this project's real prompts).
6. **Never pass a real corpus project into `prompts/few_shot.txt`.** A startup
   guard trips on this, but the guard only knows about manifest project IDs.
7. **SambaNova's free-tier rate limit (20 req/min, 20 req/day, 200,000
   tokens/day, per model) is shared account-wide only in the sense that the
   `gpt` and `opensource` slots use the same `SAMBANOVA_API_KEY`/account** —
   whether the 200,000 TPD token budget itself is independent per model or
   pooled is NOT confirmed (no rate-limit info in response headers); watch
   real failure patterns during a multi-day run rather than assuming either
   way.
