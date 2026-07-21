# LLM Risk Register Benchmark

Code and data for an IEEE conference paper: **"Evaluating Large Language Models
for Automated Risk Register Generation from Project Documentation: A Benchmark Study."**

We benchmark 3 LLMs (Claude, GPT, one open-source) across 3 prompting strategies
(zero-shot, few-shot, structured reasoning) on 21 real projects that have both
public planning documents and a published human-authored risk register (sources:
18 World Bank Project Appraisal Documents (PADs) + 3 UK government business cases,
Five Case Model format). Models see **only** planning docs;
the human register is held out as ground truth (strict no-leakage rule).

**Research questions:** RQ1 completeness/accuracy vs. humans; RQ2 variation across
models and prompts; RQ3 which risk categories LLMs miss or hallucinate (the paper's
core failure-mode contribution).

**Evaluation:** (A) semantic matching vs. ground truth (recall/precision/coverage);
(B) expert Likert ratings + Fleiss' kappa; (C) LLM-as-judge (supplementary only).

## Layout

- `data/` corpus: `raw/` (PDFs, gitignored), `processed/` (text), `ground_truth/` (JSON registers, complete for all 21 included projects - 18 World Bank PADs + 3 UK business cases), `risk_source_audit/` (excised pages, audit-only, gitignored), `corpus_manifest.csv`
- `prompts/` prompt templates + `output_schema.json` / `ground_truth_schema.json`
- `src/` `extract.py`, `run_experiments.py` (sync + batch), `match.py`, `metrics.py`, `judge.py`, `check_env.py`, `audit_corpus.py`, `build_rater_packets.py`, `validate_threshold.py` - all implemented; no full experiment run yet (needs `.env` API keys - all 3 model slots are decided and pre-filled in `.env.example`)
- `tests/` 203 unit tests covering the deterministic logic in `extract.py` (incl. the page-excision partition), `audit_corpus.py` (leakage detection), `match.py`, `metrics.py`, response parsing (`run_experiments.py`/`judge.py`), batch-API request/response shapes and submit/collect (`run_experiments.py`), Method B sampling/blinding (`build_rater_packets.py`), the run driver's append-only + leakage + cost guards, and figure rendering - stubs the embedding model, the PDF reader, and all three model APIs (sync and batch), so it runs in a few seconds with no network/keys/spend. Run `python -m unittest discover -s tests`.
- `results/` `raw_outputs/` (append-only) + `scored/` + `rater_packets/` (Method B sampling/blinding, packets pending real generations); `analysis/` figures (pipeline in progress); `paper/` (Overleaf-linked)

## Running the pipeline

**Full step-by-step sequence, flags, and known traps: [`docs/run_playbook.md`](docs/run_playbook.md).**
Short version:

```bash
python src/check_env.py                                          # verify .env keys before spending
python src/audit_corpus.py                                       # leakage audit (after any re-extract)
python src/run_experiments.py --estimate-only --runs 2 --batch   # projected cost, makes no API calls
python src/run_experiments.py --runs 2 --batch --confirm-cost    # claude+gpt batched (~50% off); opensource sync
python src/run_experiments.py --batch-check                      # poll + collect batch jobs (re-run until done)
python src/match.py --all                                        # -> results/scored/*.match.json
python src/metrics.py --scored-dir results/scored --out results/metrics.json
python analysis/make_figures.py --metrics results/metrics.json   # -> analysis/figures/
python src/judge.py --all                                        # supplementary LLM-as-judge (Method C)
python src/build_rater_packets.py --min-uk-per-cell 1 --raters 4 # Method B sampling + blinding
```

Two things to know before running: **use the venv** (bare `python` here lacks
matplotlib, so the figures step fails late), and the full grid at 2-3 runs costs
**$42-63 synchronously**, which exceeds CLAUDE.md's $30 guard. Decided
2026-07-21 (Madhu): use `--batch` (claude+gpt at ~50% off, opensource stays
synchronous) to bring 2 runs to ~$24, under the guard — see
[`results/preflight_report.md`](results/preflight_report.md) §2 for the
options this was chosen from, and
[`docs/run_playbook.md`](docs/run_playbook.md) §6a for the batch submit/check
workflow. The batch code path is tested against mocked provider responses only
— it has never been exercised against a live API call.

## Setup

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env   # then fill in API keys
```

Activate the venv before running anything — the bare `python` on PATH may be
missing `matplotlib`, which fails only at the figures step.

## Running tests

```bash
python -m unittest discover -s tests
```

203 tests, a few seconds. No API keys, network, real embedding model, or spend
needed (the sentence-transformer and all 3 model APIs, sync and batch, are
stubbed). Coverage is concentrated where this project has actually had bugs, or
where a silent failure would invalidate results: page-range parsing
(`extract.py`), greedy semantic matching (`match.py`), recall/precision/category
aggregation and the RQ-scoping variants (`metrics.py`), model/judge response
parsing — including a permanent regression test for the bool-as-int scoring bug
found and fixed 2026-07-20 — Method B sampling determinism and **blinding
integrity** (`build_rater_packets.py`), the run driver's append-only,
reproducibility, leakage, and cost guards, and the batch-API request/response
shapes and submit/collect cycle against `_finalize_run` (`run_experiments.py`).

See `CLAUDE.md` for frozen research questions and methodology rules, and
`INCLUSION_CRITERIA.md` for corpus selection. Status: corpus (21/21) and
pipeline are complete and unit-tested; Method A's matching threshold is
validated against a hand-labeled set; Method B's sampling/blinding is built;
all 3 model slots are decided (`.env.example`); the run driver has been
pre-flighted end to end with stubbed providers (`results/preflight_report.md`)
and now supports batched claude+gpt runs (`--batch`/`--batch-check`) to bring
the decided 2-run grid under the $30 cost guard. Remaining before a full run:
real `.env` API keys and human-rater recruitment for Method B (target: full
experiment run by end of August 2026).
