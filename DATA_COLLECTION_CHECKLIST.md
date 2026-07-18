# Data Collection Checklist - Validation Batch (5 World Bank + 5 UK IPA)

Goal: hand-pick **5 World Bank** and **5 UK** projects that each have (a) a public
planning/appraisal document and (b) a published human-authored risk register that
we can extract as JSON - WITHOUT the register leaking into the planning text.
This 10-document batch validates ground-truth quality before we build the rest of
the pipeline. Fill one row per project in `data/corpus_manifest.csv`.

> **Decision to lock during this batch (important):** for each source, we must
> define exactly which text is the *planning input* (goes to models) and which is
> the *ground-truth register* (held out). My recommended mapping is below; confirm
> or change it once you have eyes on 2-3 real documents.

---

## Per-document workflow (do this for all 10)

1. [ ] Find a candidate project and open its document(s).
2. [ ] Confirm a **planning/appraisal** section exists (project description,
       components, financing, implementation arrangements).
3. [ ] Confirm a **human risk register / risk matrix** exists and is structured
       enough to map to our schema (description, category, likelihood, impact,
       mitigation - partial is OK, note gaps).
4. [ ] **Leakage check (manual excision):** locate the risk section and remove it
       from the planning text; record the exact page range(s) in `pages_excised`.
       Then skim the remaining text for narrative "Key Risks" prose that echoes
       the register and remove/note it. If planning + register are inseparable,
       **exclude** (see `INCLUSION_CRITERIA.md` -> leakage control protocol).
5. [ ] Download the source PDF(s) into `data/raw/<project_id>/` (gitignored).
6. [ ] Record the row in `data/corpus_manifest.csv`: `project_id`, `source`,
       `project_name`, `doc_urls` (planning only, `|`-separated), `register_url`,
       `publication_date` (for contamination analysis), `pages_excised`,
       `language`, `sector`, `inclusion_status`, `notes`. Prefer post-2024
       documents where a choice exists, but capture the date regardless.
7. [ ] Manually transcribe the register into `data/ground_truth/<project_id>.json`
       (structure it now even if by hand; this is the validation of quality).

Suggested ids: `WB01`-`WB05` (World Bank), `UK01`-`UK05` (UK IPA).

---

## Source A - World Bank (5 projects)

**Entry points (stable portals):**
- Projects & Operations: <https://projects.worldbank.org/en/projects-operations/projects-home>
- Documents & Reports: <https://documents.worldbank.org/en/publication/documents-reports/documentlist>

**How to search:**
1. In Documents & Reports, set **Document Type = "Implementation Completion and
   Results Report" (ICR)** to find completed projects that are well documented.
2. From the ICR, open the **same project's project page** on projects.worldbank.org
   and download the **PAD (Project Appraisal Document)** - this is the planning doc.
3. Prefer projects that are: English, non-trivial scale (larger IBRD/IDA loans),
   and spread across sectors (transport, energy, water, health, education).

**Recommended planning-vs-register mapping for World Bank:**
- **Planning input (to model):** the PAD project description, components,
  institutional/implementation arrangements, and financing - **with the PAD's own
  risk section removed** (the SORT / "Systematic Operations Risk-rating Tool"
  table and any risk matrix).
- **Ground-truth register (held out):** the PAD's **SORT risk table / risk
  matrix** (risk categories + ratings), optionally cross-checked against the ICR's
  account of risks that materialized.
- ⚠️ Because both live in the PAD, step 4 (leakage separability) is the crux here.
  If you cannot confidently strip the risk section from the planning text,
  exclude the project.

**Checklist:**
- [ ] WB01 - PAD downloaded, SORT/risk table located, separable? recorded
- [ ] WB02 - "
- [ ] WB03 - "
- [ ] WB04 - "
- [ ] WB05 - "  (aim for sector spread across the five)

---

## Source B - UK IPA / major projects (5 projects)

**Entry points (stable portals):**
- IPA / GMPP major projects data: <https://www.gov.uk/government/collections/major-projects-data>
- gov.uk full search (find published registers/business cases):
  <https://www.gov.uk/search/all?keywords=risk%20register>
- National Audit Office reports (often summarize project risks):
  <https://www.nao.org.uk/reports/>

**How to search:**
1. Use gov.uk search for `"risk register"` or `"programme business case"` scoped
   to a department/programme to find a **published human risk register**.
2. For the **planning input**, use the same programme's published **business case**
   (Green Book five-case model - strategic/economic/commercial/financial/management
   cases) or IPA/departmental project description, excluding its risk section.
3. GMPP annual reports give Delivery Confidence Assessments but usually **not** a
   full risk register - use them to identify candidate programmes, then find the
   register/business case separately.

**Recommended planning-vs-register mapping for UK:**
- **Planning input (to model):** business-case narrative (strategic/economic/
  management cases minus risk), or IPA project description.
- **Ground-truth register (held out):** the separately published risk register or
  the business case's risk register appendix.

**Candidate programmes to check first** (verify each actually has BOTH a planning
doc and a published register before committing - do not assume):
- [ ] UK01 - candidate: a major transport programme (e.g. HS2 / Crossrail-type)
- [ ] UK02 - candidate: a major digital/IT programme (e.g. Emergency Services Network)
- [ ] UK03 - candidate: a welfare/service programme (e.g. Universal Credit)
- [ ] UK04 - candidate: a defence or health infrastructure programme
- [ ] UK05 - candidate: an energy/environment programme (sector spread)

> These are *starting points to investigate*, not confirmed sources. Record the
> real, resolving URLs in the manifest only after you have opened the documents.

---

## Done when

- [ ] 10 rows in `corpus_manifest.csv` with `inclusion_status = included`.
- [ ] 10 PDFs (or PDF sets) saved under `data/raw/<id>/`.
- [ ] 10 hand-built `data/ground_truth/<id>.json` registers.
- [ ] Planning-vs-register mapping confirmed for each source (leakage boundary clear).

Once this passes, we build `run_experiments.py`, `match.py`, `metrics.py`, `judge.py`.
