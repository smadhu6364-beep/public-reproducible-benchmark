# Corpus Inclusion Criteria

A candidate project is included only if it passes **all** checks below. Record the
outcome in `data/corpus_manifest.csv` (`inclusion_status` = `included` /
`excluded` / `candidate`; if excluded, fill `exclusion_reason`).

## Checklist (all must be YES to include)

- [ ] **Planning docs complete.** Public, appraisal/planning-stage document(s)
      exist that describe the project *before or independently of* outcomes
      (e.g. World Bank PAD/appraisal sections, UK business case / IPA project
      description). Enough substance to plausibly reason about risks.
- [ ] **Human risk register extractable.** A published, human-authored risk
      register (or clearly-structured risk section) exists and can be extracted
      into the fixed JSON schema (risk_id, description, category, likelihood,
      impact, mitigation). For World Bank PADs this is the "V. Key Risks and
      Mitigation Measures" section plus the SORT table in the Data Sheet. Partial
      fields are OK if description + category are present; note gaps in `notes`.
- [ ] **English.** Primary documents and the register are in English
      (`language` = `en`). Translations are not used (avoids translation noise).
- [ ] **Project scale.** Non-trivial project with a real risk profile
      (major/complex programme or sizeable investment). Exclude tiny or
      purely administrative items with no meaningful risk content.
- [ ] **No doc-register leakage risk.** The planning document(s) fed to models
      must NOT themselves contain the ground-truth risk register or a near-copy
      of it. If planning and register live in the same PDF, they must be
      cleanly separable so the register can be removed before extraction.
      If they cannot be separated with confidence, **exclude**.

## Additional recording rules

- **`doc_urls`**: if a project has multiple planning documents, separate URLs
  with a pipe `|` inside the quoted CSV field. Only planning/appraisal docs go
  here - never the register URL.
- **`register_url`**: the source of the human risk register (ground truth).
  Keep this separate from `doc_urls` so the leakage boundary is explicit.
- **`publication_date`**: publication date of the planning document (YYYY-MM or
  YYYY-MM-DD). Needed for the pretraining-contamination analysis below.
- **`pages_excised`**: the page range(s) of the risk section removed from the
  planning text before it is fed to models (see leakage control protocol).
  Example: `PAD pp. 61-63 (SORT table)`. This is the audit trail.
- **`sector`**: short tag (e.g. transport, energy, health, water, ICT, education).
- **Provenance**: for every included project, save the raw PDF(s) locally under
  `data/raw/` (gitignored) and confirm the URL still resolves on the record date.

## Leakage control protocol (manual excision, not automated)

At n=20 the defensible approach is **manual** excision, not automated section
stripping. Automated detection across PAD formats spanning many years will fail
silently; manual is slower but auditable. For each included project:

1. **Excise the register.** Identify the risk section (for World Bank PADs: the
   "V. Key Risks and Mitigation Measures" section and the SORT table in the Data
   Sheet) and remove it from the planning text that will be fed to models.
   Record the exact page range(s) in `pages_excised`.
2. **Skim for prose echoes.** PADs often restate SORT content in narrative "Key
   Risks" prose elsewhere in the document. Skim the remaining text and remove or
   note any passage that enumerates the register's risks. Record what you found
   in `notes`.
3. **Keep the register as ground truth only.** The excised risk content becomes
   `data/ground_truth/<project_id>.json` and must never re-enter a prompt or a
   few-shot example (including for a *different* project).

This audit trail is written up in the paper as a "leakage control protocol"
paragraph (see `paper/methodology_notes.md`) - a documented control reviewers
can trust, rather than an automated step they must take on faith.

## Pretraining contamination (public documents)

These are public documents; the models may have seen the full PADs - risk tables
included - during pretraining. Excision cannot fix that. Two mitigations, use both:

- **Prefer post-cutoff documents.** Where possible, prefer projects whose
  documents were published **after the models' training cutoffs** (roughly 2024
  onward; verify the exact cutoff per chosen model). This will not be achievable
  for all 20 - do not force it - but capture `publication_date` for every project.
- **Test pre- vs post-cutoff.** With `publication_date` recorded, we can run a
  free supplementary analysis: does performance differ on pre- vs post-cutoff
  documents? A gap is itself a contamination signal worth reporting.
- **Name it as a limitation.** Contamination is written into the paper's
  limitations section from day one (see `paper/methodology_notes.md`). Every
  benchmark on public data has this issue; naming it ourselves is what gets a
  paper through review.

## Target

~20 included projects, balanced across the two sources (World Bank PADs and
UK IPA/GMPP reports) and across sectors where possible. Begin with a
10-document validation batch (5 + 5) before scaling.
