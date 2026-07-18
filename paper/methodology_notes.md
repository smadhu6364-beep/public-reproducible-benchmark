# Methodology Notes (working drafts for the paper)

Seed text for Methods + Limitations. Refine before writing; keep grounded in
what we actually did. Overleaf holds the real manuscript; this is scratch.

## Leakage control protocol (Methods)

> Draft paragraph:
> Because several source documents (notably World Bank Project Appraisal
> Documents) contain the human risk register within the same PDF as the planning
> narrative, we applied a manual leakage-control protocol rather than automated
> section detection, which is unreliable across document formats spanning many
> years. For each project, an author located the risk section (e.g. the SORT risk
> table) and excised it from the text supplied to the models, recording the exact
> page range removed. The remaining planning text was then skimmed for narrative
> passages that restate the register's risks ("Key Risks" prose), which were
> likewise removed. The excised register was retained only as held-out ground
> truth. Page ranges and prose-removal notes are recorded per project in the
> corpus manifest, providing an auditable trail of the planning/ground-truth
> boundary.

Cross-refs: `INCLUSION_CRITERIA.md` (protocol steps), `data/corpus_manifest.csv`
(`pages_excised`, `notes`).

## Pretraining contamination (Limitations)

> Draft paragraph:
> Our corpus is drawn from public documents, which the evaluated models may have
> encountered during pretraining - including the very risk registers we hold out
> as ground truth. Excision controls what enters the prompt but cannot control
> what a model already learned. We mitigate this in two ways. First, where a
> choice existed we preferred projects whose documents were published after the
> models' training cutoffs, and we record each document's publication date.
> Second, we report a supplementary analysis comparing performance on pre- versus
> post-cutoff documents; a systematic gap would indicate contamination effects.
> We nonetheless flag contamination as a genuine limitation: like all benchmarks
> built on public data, absolute scores may be optimistic, and results should be
> read as relative comparisons across models and prompting strategies rather than
> as contamination-free absolute capability estimates.

Cross-refs: `INCLUSION_CRITERIA.md` (contamination section),
`data/corpus_manifest.csv` (`publication_date`).

## Structured-reasoning output contract (Methods / reproducibility note)

The `structured` prompt condition asks the model to emit visible step-by-step
reasoning followed by a `FINAL JSON:` marker and a single JSON object; the
`zero_shot` and `few_shot` conditions emit the JSON object only. The experiment
runner must therefore, for the structured condition, extract the JSON that
follows the last `FINAL JSON:` marker. This is the one output-contract difference
between conditions and should be stated for reproducibility. (Open design point:
if we later prefer identical parsing across all three conditions, switch the
structured prompt to JSON-only output and move the reasoning to internal only.)
