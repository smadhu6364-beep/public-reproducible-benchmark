# LLM Risk Register Benchmark

Code and data for an IEEE conference paper: **"Evaluating Large Language Models
for Automated Risk Register Generation from Project Documentation: A Benchmark Study."**

We benchmark 3 LLMs (Claude, GPT, one open-source) across 3 prompting strategies
(zero-shot, few-shot, structured reasoning) on ~20 real projects that have both
public planning documents and a published human-authored risk register (sources:
World Bank Project Appraisal Documents (PADs), UK IPA/GMPP reports). Models see **only** planning docs;
the human register is held out as ground truth (strict no-leakage rule).

**Research questions:** RQ1 completeness/accuracy vs. humans; RQ2 variation across
models and prompts; RQ3 which risk categories LLMs miss or hallucinate (the paper's
core failure-mode contribution).

**Evaluation:** (A) semantic matching vs. ground truth (recall/precision/coverage);
(B) expert Likert ratings + Fleiss' kappa; (C) LLM-as-judge (supplementary only).

## Layout
- `data/` corpus: `raw/` (PDFs, gitignored), `processed/` (text), `ground_truth/` (JSON registers, complete for all 21 included projects - 18 World Bank PADs + 3 UK business cases), `risk_source_audit/` (excised pages, audit-only, gitignored), `corpus_manifest.csv`
- `prompts/` prompt templates + `output_schema.json` / `ground_truth_schema.json`
- `src/` `extract.py`, `run_experiments.py`, `match.py`, `metrics.py`, `judge.py` - all implemented; no full experiment run yet (needs `.env` API keys + a model-tier decision - see `.env.example`)
- `results/` `raw_outputs/` (append-only) + `scored/`; `analysis/` figures; `paper/` (Overleaf-linked)

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

See `CLAUDE.md` for frozen research questions and methodology rules, and
`INCLUSION_CRITERIA.md` for corpus selection. Status: corpus collection +
pipeline validation (target: full experiment run by end of August 2026).
