# Run playbook — the full experiment, end to end

The ordered command sequence for producing the paper's results, with the flags
that matter and the traps that have actually bitten this project. Written
2026-07-21; every command below was run (or `--help`-verified) against the repo
as it stands, so the flags are real, not remembered.

Read `CLAUDE.md` first for the frozen research questions and methodology rules.
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
cp .env.example .env      # then fill in the three keys
python src/check_env.py   # verifies each provider actually answers
```

`.env.example` is already pre-filled with the decided model triple
(`claude-sonnet-5`, `gpt-5.6-terra`,
`meta-llama/Llama-3.3-70B-Instruct-Turbo` via Together AI) — you are filling in
*keys*, not choosing models. `.env` is gitignored and must stay that way.

`check_env.py` reports per-provider `CONFIGURED` / `RESULT`. Do not proceed to
step 6 until all three say configured and reachable — a systemic key failure
mid-grid wastes real money on the calls that did work.

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

## 5. Cost estimate — always, before spending

```bash
python src/run_experiments.py --estimate-only --runs 2
python src/run_experiments.py --estimate-only --runs 2 --batch   # see below
```

Prints per-model and total projected cost, makes **no API calls**. Measured
2026-07-21 for the decided triple: **$21.05 per run** across 189 cells →
**$42.11 at 2 runs, $63.16 at 3** (synchronous pricing).

**Both 2-run and 3-run configurations exceed CLAUDE.md's $30 cost guard at
synchronous pricing**, while CLAUDE.md also specifies "2-3 runs each". Decided
2026-07-21 (Madhu): build batch support, then run 2 at the batched rate — see
§6a. `results/preflight_report.md` §2 has the full options analysis this
decision was made from.

## 6. The grid

Two ways to run it. Both write identically-shaped records to
`results/raw_outputs/` and `results/run_config.jsonl` — nothing downstream
(§7 onward) can tell which path produced a given run.

### 6a. Batched (the decided path — claude+gpt at ~50% off)

```bash
python src/run_experiments.py --runs 2 --batch   # ~$24.01, clears the $30 guard, no --confirm-cost needed
python src/run_experiments.py --batch-check      # poll + collect, any time, any # of times
```

**Correction 2026-07-21: `--confirm-cost` is *not* required for this command.**
A previous version of this doc claimed it was. Verified directly: ran this exact
command (real 189-cell grid, `--runs 2 --batch`, no `.env`/keys) and it printed
the real batch-discounted estimate (`estimated_total_usd: 24.01`) and proceeded
straight past the cost-guard check — it only stopped afterward on the expected
`ANTHROPIC_API_KEY is not set` error, not on the guard. `main()`'s guard check
(`estimate_cost(..., batch_labels=BATCH_ELIGIBLE_LABELS if args.batch else
frozenset())`) already applies the batch discount before comparing to $30, so
$24.01 correctly clears it without an override. `--confirm-cost` is harmless to
add anyway (it's a no-op below the threshold) but isn't load-bearing here.

- `--batch` submits claude+gpt cells to Anthropic's and OpenAI's batch APIs
  (~50% off list) and **exits immediately** — it does not wait. Batch jobs can
  take up to 24h (Anthropic is often faster; OpenAI's `completion_window` is a
  fixed 24h). The opensource/Together AI slot is **not** batched — its
  batch-discount availability was never verified, so it still runs
  synchronously in the same invocation, at list price, before `--batch`
  returns.
- `--batch-check` polls every job recorded in `results/batch_jobs.json` and
  collects any that finished. **Safe to re-run any number of times** —
  already-collected jobs and already-written rows are both skipped, not
  reprocessed. Run it again later (a new terminal, tomorrow, whenever) until
  every job shows `"status": "collected"`.
- `results/batch_jobs.json` is the batch equivalent of a to-do list against the
  provider APIs — it is how `--batch-check` knows what to look for. Don't
  delete it until every job is collected.
- Real SDK shapes were confirmed against the installed `anthropic`/`openai`
  packages but **never exercised against a live batch call** — see
  `run_experiments.py`'s module docstring. Spot-check `batch_jobs.json` and the
  first few batch-sourced `raw_outputs/*.json` records by hand the first time
  this runs for real.

### 6b. Synchronous (all 3 models, one call per run)

```bash
python src/run_experiments.py --runs 2 --confirm-cost   # ~$42, needs --confirm-cost
```

- `--confirm-cost` is **required** whenever the estimate exceeds $30. Without it
  the run exits 1 having written nothing (verified).
- `--temperature` defaults to 0.1 and is hard-limited to [0, 0.2] per CLAUDE.md.
- Raw outputs are **append-only**: `next_free_run_index` picks the lowest unused
  index, and `run_one` refuses to overwrite an existing file. Re-invoking adds
  runs rather than clobbering them — which also means a partial grid is safe to
  resume by just running the command again.
- Scope it down while smoke-testing: `--project P-SRB-CompetitivenessJobs
  --model claude --prompt zero_shot --runs 1` is one call, a few cents.
- Exit codes: `2` = every call failed (systemic — bad keys/network, treat as "no
  run happened"); `3` = some failed; `1` = cost guard.

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

Supplementary evidence per CLAUDE.md — never a headline result. The judge never
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

## Tests

```bash
python -m unittest discover -s tests
```

203 tests, ~3.5s, **no network, no API keys, no spend** — the embedding model,
the PDF reader, and all three providers (sync AND batch) are stubbed. Run this
before and after touching anything in `src/`. Coverage is concentrated where
this project has actually had bugs or where a silent failure would invalidate
results:

| File | Protects |
| --- | --- |
| `test_extract.py` | manifest page-range parsing (source of the Serbia/Uganda bugs) |
| `test_extract_excision.py` | the excision partition itself — every page in exactly one output, 1-indexing, leakage guards |
| `test_audit_corpus.py` | the leakage auditor's **false-negative** surface + a real-corpus regression |
| `test_match.py` | greedy one-to-one matching, threshold boundary |
| `test_metrics.py` | recall/precision guards, subgroup separation, scoping variants |
| `test_parsing.py` | model + judge response parsing, incl. the bool-as-int regression |
| `test_rater_packets.py` | sampling determinism, UK stratification, **blinding integrity** |
| `test_run_pipeline.py` | append-only, reproducibility fields, leakage guard, cost estimator |
| `test_batch.py` | batch request/response shapes vs. real SDK contracts, submit/collect against `_finalize_run`, batch cost discount |
| `test_figures.py` | figure rendering + the metrics.json ↔ make_figures key contract |

`test_figures.py` needs matplotlib and **skips** (does not fail) on an
interpreter without it — so `python -m unittest discover -s tests` is green
either way, which is also why §0's venv warning matters.

## Things that will bite you

1. **Bare `python` lacks matplotlib.** Activate the venv (§0).
2. **The $30 guard vs. "2-3 runs" conflict is resolved via `--batch`** (§6a) —
   but the batch code path has never been exercised against a live provider
   call. Spot-check the first real `--batch-check` collection by hand.
3. **`.env` does not exist yet** — nothing in steps 6/8 can run until it does.
4. **Raw outputs are append-only.** If you want a clean re-run you must move the
   old files aside deliberately; nothing overwrites them for you. This applies
   identically to batch-collected runs.
5. **Sonnet 5's introductory pricing ends 2026-08-31**, the same month as the
   project deadline. Slipping past it raises claude's share ~50% either way,
   batched or not.
6. **Never pass a real corpus project into `prompts/few_shot.txt`.** A startup
   guard trips on this, but the guard only knows about manifest project IDs.
7. **`--batch` submits and returns immediately; it does not wait.** Forgetting
   to come back with `--batch-check` means the grid never actually lands in
   `results/raw_outputs/`, even though the terminal shows no error.
