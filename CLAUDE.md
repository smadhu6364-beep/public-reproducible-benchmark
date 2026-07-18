Project: LLM Risk Register Benchmark (IEEE Paper)

## What this repo is

Code and data for an independent IEEE conference paper:
"Evaluating Large Language Models for Automated Risk Register Generation
from Project Documentation: A Benchmark Study"

Authors: Madhu (pipeline, experiments, metrics) and Kruthik (lit review,
evaluation protocol, raters, writing). Target: IEEE TEMS-family conference,
submission ~Feb-Mar 2027. IEEE two-column format, 6-8 page limit.

## Research questions (FROZEN - never modify or reinterpret)

RQ1: How complete/accurate are LLM-generated risk registers vs. human-authored ones?
RQ2: How do results vary across 3 models (Claude, GPT, one open-source) and
3 prompting strategies (zero-shot, few-shot, structured reasoning)?
RQ3: Which risk categories do LLMs systematically miss or hallucinate?
(Failure-mode analysis = the paper's core contribution.)

## Methodology rules (enforce in all code you write)

- Corpus: ~20 real projects with BOTH public planning docs AND a published
  human risk register. Sources: World Bank ICR reports, UK IPA/GMPP reports.
- LEAKAGE RULE (critical): models only ever receive planning/appraisal
  documents. The file containing the real risk register must never enter a
  prompt, a context window, or a few-shot example drawn from the same project.
- Grid: 3 models x 3 prompts x 20 projects, 2-3 runs each, temperature 0-0.2.
- Reproducibility: every run logs model version string, run date, temperature,
  prompt file SHA256, into results/run_config.jsonl.
- Raw model outputs in results/raw_outputs/ are append-only. Never overwrite.
- Output schema (fixed JSON per risk): risk_id, description, category
  (technical | financial | schedule | stakeholder | political_regulatory |
  environmental | organizational | external), likelihood (1-5), impact (1-5),
  mitigation.
- Evaluation: (A) semantic matching vs. ground truth - recall, precision,
  per-category coverage; (B) expert Likert ratings + Fleiss' kappa;
  (C) LLM-as-judge, supplementary only.

## Repo structure (maintain exactly)

    data/raw/            original PDFs (gitignored)
    data/processed/      extracted text per project
    data/ground_truth/   human risk registers as structured JSON
    data/corpus_manifest.csv
    prompts/             zero_shot.txt, few_shot.txt, structured.txt, output_schema.json
    src/                 extract.py, run_experiments.py, match.py, metrics.py, judge.py
    results/raw_outputs/ (append-only)
    results/scored/
    analysis/figures/
    paper/               (Overleaf-linked, not stored here)

## Coding standards

- Python 3.11+, venv, requirements.txt pinned versions.
- Libraries: PyMuPDF (pdf extraction), anthropic, openai, sentence-transformers,
  pandas, scikit-learn, matplotlib. Ask before adding anything else.
- API keys only via .env (python-dotenv). .env is gitignored; keep .env.example updated.
- Small, reviewable commits with clear messages. Never commit data/raw or .env.
- Cost guard: before any full-grid run, print a token/cost estimate and STOP
  for confirmation if projected cost > $30.

## Hard rules

- Never fabricate data, citations, metrics, or results. Unknown = say unknown.
- Never expand scope (extra models, metrics, datasets) without asking first.
- Timeline: corpus + pipeline + full experiment run must complete by end of
  August 2026. Prefer working code today over elegant code next week.
