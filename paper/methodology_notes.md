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
(`sort_pages`, `section_v_pages`, `notes`).

> **Correction 2026-07-21:** this cross-ref previously named a `pages_excised`
> column, which does not exist in `corpus_manifest.csv`. Checked against the
> real header row: the columns `extract.py._load_excision_pages()` actually
> reads and unions to decide what to excise are `sort_pages` and
> `section_v_pages` (there is also a `proposed_excision_pages` column, but it
> is not the one the code reads - don't cite it as authoritative here).

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

> **Gap flagged 2026-07-21, not fixed - a methodology decision, not mine to
> make silently:** two claims in the paragraph above don't yet hold.
>
> 1. **UPDATE 2026-07-21 (later same day): the comparison code now exists**
>    (`metrics.pretraining_cutoff_report()`, 5 tests in `tests/test_metrics.py`
>    `TestPretrainingCutoffReport`), but is deliberately **opt-in, not wired
>    into `compute_all()`**, because it needs one input this session must not
>    invent: `model_cutoffs = {"claude": "YYYY-MM-DD", "gpt": "...",
>    "opensource": "..."}`. Each model's actual training-data cutoff is a
>    real, provider-published fact tied to whichever specific model version
>    ends up in `.env` - sourcing it is a quick lookup once that's finalized,
>    not a research question, but it's still a fact to source, not a default
>    to hardcode. Whoever finalizes the model versions should look up each
>    one's stated cutoff and pass it in; the function buckets every run into
>    pre_cutoff / post_cutoff / undated (a project with no `publication_date`
>    is excluded from both, never guessed) and reports recall/precision per
>    bucket. See finding 2 below for why "undated" will be large today.
> 2. **`publication_date` is populated for only 10 of the 21 included
>    projects.** Checked directly against `corpus_manifest.csv`: the other 11
>    have that field blank, and 10 of those 11 have `approval_date` blank too
>    - there is no usable date at all for roughly half the corpus. Even once
>    the analysis above exists, its pre/post split could only be computed for
>    the projects that actually carry a date. Backfilling dates (where
>    findable) or deciding how to handle undated projects (exclude from just
>    this supplementary analysis? Leave the field aspirational and drop this
>    paragraph's specific claim?) is a call for whoever owns
>    `corpus_manifest.csv`.
>
>    **Checked for a safe auto-backfill, 2026-07-21 - found one, and rejected
>    it, don't repeat this:** all 10 undated projects' PADs contain an
>    "Expected Approval Date" field in their extracted text
>    (`data/processed/*.txt`), and it's mechanically extractable (a reliable
>    label-then-values pattern, confirmed across 6 of the 10 by hand: e.g.
>    P-BGD-SocialProtectionResilience -> `26-Mar-2025`,
>    P-JOR-InnovativeStartupsSMEsFund2 -> `31-Mar-2025`). **This is the wrong
>    field and must not be used to fill `publication_date`.** Checked against
>    the 10 *already-populated* rows: `publication_date` sits days-to-weeks
>    *before* `approval_date` for the same project (e.g. P-PER-ArequipaColca:
>    pub `2026-06-16`, approval `2026-07-09`) - it evidently records when the
>    World Bank posted the *document* (portal metadata), not a Board-approval
>    event. The PAD's internal "Expected Approval Date" is a third, different
>    thing again: a projection made at drafting time, which may predate,
>    postdate, or never match the real approval outcome. Filling
>    `publication_date` with it would silently substitute the wrong concept
>    under the right-sounding column name - worse than leaving the field
>    blank. A real fix needs either the actual World Bank document-portal
>    publication metadata (not present in any file already in this repo) or a
>    human decision to redefine what this analysis needs. Not attempted
>    further.

## Structured-reasoning output contract (Methods / reproducibility note)

The `structured` prompt condition asks the model to emit visible step-by-step
reasoning followed by a `FINAL JSON:` marker and a single JSON object; the
`zero_shot` and `few_shot` conditions emit the JSON object only. The experiment
runner must therefore, for the structured condition, extract the JSON following
the `FINAL JSON:` marker. This is the one output-contract difference between
conditions and should be stated for reproducibility. (Open design point: if we
later prefer identical parsing across all three conditions, switch the
structured prompt to JSON-only output and move the reasoning to internal only.)

> **Correction 2026-07-21:** the sentence above previously said "the JSON that
> follows the **last** `FINAL JSON:` marker" - checked against
> `run_experiments.py`'s actual regex (`_FINAL_JSON_RE`,
> `r"FINAL JSON:\s*(\{.*\})\s*\Z"`) and confirmed empirically: it anchors to
> the FIRST `FINAL JSON:` occurrence and captures greedily to the end of the
> string, not the last occurrence. In the well-behaved case (exactly one
> marker, as the prompt instructs) this distinction is invisible. But if a
> response ever contains the marker twice - e.g. a model second-guessing
> itself mid-answer - the two behaviors diverge, and verified directly: the
> real code does NOT recover the second/final JSON object in that case, it
> fails to parse entirely (`json.loads` raises "Extra data", the bare-JSON
> fallback also fails because the same greedy span is captured). If this
> parse-failure mode ever shows up in real run data, it will look like a
> generic structured-prompt parse failure, not specifically "picked the wrong
> marker" - worth knowing if failure-mode counts for the `structured` prompt
> condition look surprising in RQ2/RQ3.
