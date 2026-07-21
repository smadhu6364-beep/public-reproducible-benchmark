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
- `src/` `extract.py`, `run_experiments.py`, `match.py`, `metrics.py`, `judge.py`, `check_env.py`, `audit_corpus.py`, `build_rater_packets.py`, `validate_threshold.py` - all implemented; no full experiment run yet (needs `.env` API keys - all 3 model slots are decided and pre-filled in `.env.example`)
- `tests/` unit tests for the pure/deterministic logic in `extract.py`, `match.py`, `metrics.py`, and response parsing (`run_experiments.py`/`judge.py`) - stubs the embedding model and API calls, so it runs fast with no network/keys. Run `python3 -m unittest discover -s tests`.
- `results/` `raw_outputs/` (append-only) + `scored/` + `rater_packets/` (Method B sampling/blinding, packets pending real generations); `analysis/` figures (pipeline in progress); `paper/` (Overleaf-linked)

## Running the pipeline
```
python3 src/extract.py --all                       # regenerate data/processed/ from data/raw/
python3 src/run_experiments.py --estimate-only      # see projected cost before spending anything
python3 src/run_experiments.py --confirm-cost       # full grid (needs .env configured first)
python3 src/match.py --all                          # score raw_outputs/ against ground truth
python3 src/metrics.py --scored-dir results/scored  # recall/precision/coverage report
python3 src/judge.py --all                          # supplementary LLM-as-judge (Method C)
```

## Setup
```
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env   # then fill in API keys
```

## Running tests
```
python3 -m unittest discover -s tests
```
Unit tests only - no API keys, network, or real embedding model needed
(the sentence-transformer and the 3 model APIs are stubbed). Covers the
pure logic most prone to silent bugs in this project's own history:
page-range parsing (`extract.py`), greedy semantic matching (`match.py`),
recall/precision/category aggregation (`metrics.py`), and model/judge
response parsing (`run_experiments.py`/`judge.py`) - including a permanent
regression test for the bool-as-int scoring bug found and fixed 2026-07-20.

See `CLAUDE.md` for frozen research questions and methodology rules, and
`INCLUSION_CRITERIA.md` for corpus selection. Status: corpus (21/21) and
pipeline are complete and unit-tested; Method A's matching threshold is
validated against a hand-labeled set; Method B's sampling/blinding is built;
all 3 model slots are decided (`.env.example`). Remaining before a full run:
real `.env` API keys, and human-rater recruitment for Method B (target:
full experiment run by end of August 2026).
