# data/

- `raw/` - original source PDFs. **Gitignored** (see `.gitignore`); never committed.
  Keep a local copy; the download provenance lives in `corpus_manifest.csv`.
- `processed/` - cleaned plain text per project, produced by `src/extract.py`.
- `ground_truth/` - human-authored risk registers as structured JSON. These are
  held out: per the LEAKAGE RULE they must never enter a prompt or few-shot
  example for the same project.
- `corpus_manifest.csv` - one row per candidate project with source, URLs, and
  inclusion status. See `../INCLUSION_CRITERIA.md`.
