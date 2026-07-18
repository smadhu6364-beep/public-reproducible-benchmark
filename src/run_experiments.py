"""run_experiments.py - drive the 3 models x 3 prompts x ~20 projects grid.

NOT YET IMPLEMENTED. Deferred until the 10-document ground-truth validation
passes (see README + CLAUDE.md). Do not implement without approval.

Planned responsibilities:
  - Load processed planning text per project (data/processed/).
  - Enforce the LEAKAGE RULE: never load data/ground_truth/<project> into a
    prompt or few-shot example for the same project.
  - For each (model, prompt, project, run): call model at temperature 0-0.2,
    append raw output to results/raw_outputs/ (append-only), and log
    {model_version, run_date, temperature, prompt_sha256} to
    results/run_config.jsonl.
  - Cost guard: print token/cost estimate before a full-grid run and STOP for
    confirmation if projected cost > $30.
"""

raise NotImplementedError(
    "run_experiments.py is deferred until the 10-document validation passes."
)
