# Aladağ, H. (2023): "Assessing the Accuracy of ChatGPT Use for Risk Management in Construction Projects"

**Venue:** Sustainability (MDPI), Vol. 15, No. 22, Article 16071. Open access.
**Source used:** Full text (Sections 1–4: Introduction, Related Work, Methodology, Results) read
directly from the publisher page. Section 5 (Discussion/Limitations/Recommendations) did not load
in the fetch and was **not** read; see "What's unverified" below.
**Cite key in this project's `references.bib`:** `aladag2023assessing_chatgpt`

## Method
Two-phase design. Phase 1: a literature-derived set of Key Performance Indicators (KPIs) covering
each risk-management sub-process (identification, analysis, response, monitoring). Phase 2: a
questionnaire of prompt templates was used to converse with ChatGPT about two case scenarios; a
PPP-type transportation project and a PPP-type energy project (no real project documents, no
real published risk register). ChatGPT's responses were then scored by construction experts in
focus-group sessions on a 7-point Likert scale (1 = very low to 7 = very high), per KPI.

## Sample size
- Pilot/questionnaire validation: 2 respondents (1 PMP with 12 years' experience, 1 academic).
- Main evaluation: 2 focus groups of 5 experts each (10 experts total); one group for the
  transportation scenario, one for the energy scenario.
- Only 2 scenarios total, both hypothetical/illustrative, not real projects with real published
  registers.

## Evaluation design
Expert consensus scoring (not individual scoring averaged) of ChatGPT's own output, KPI by KPI,
on a 7-point accuracy/quality Likert scale. This is an **opinion-based** evaluation; there is no
comparison against a real, independently authored risk register for the same project. Single LLM
only (ChatGPT); the exact version/date is not stated in the sections read.

## Stated limitations
**Not directly confirmed**: the paper's own Section 5 ("Discussion... limitations and
recommendations for further studies," per the Introduction's own roadmap) did not load during
fetch. Based on the methodology actually used (Sections 1–4), the following limitations are
self-evident from the design itself, but are **my inference, not a quoted limitations list**:
single LLM/version, only 2 hypothetical case scenarios, small expert panel (10 total), no
comparison to a real published register, opinion/Likert-based rather than ground-truth-based
scoring.

## What's unverified
Section 5 (Discussion, Limitations, Recommendations) and Table 10 (final summary table) were not
captured by the fetch tool used (the page content cut off mid-Results). If a word-for-word
"stated limitations" quote is needed for the paper, this section should be re-fetched or read
directly from `https://www.mdpi.com/2071-1050/15/22/16071`.

## How this study differs
Aladağ evaluates ChatGPT's plausibility against expert opinion on 2 hypothetical scenarios. This
project instead measures semantic-matching recall/precision/category-accuracy against 21 real,
published, independently authored risk registers across 3 models and 3 prompting strategies;
addressing the "no real ground truth" and "single-model" gaps directly.
