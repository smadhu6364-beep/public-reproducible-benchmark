# "Large Language Models for Construction Risk Classification: A Comparative Study" (2025)

**Venue:** Buildings (MDPI), Vol. 15, No. 18, Article 3379. Open access. Authors (from the paper's
own Author Contributions statement, initials A.E. and H.K.) are consistent with this project's
existing internal shorthand "Erfani and Khanjar" used in earlier project notes.
**Source used:** Full text read directly from the publisher page, including the Conclusions,
Author Contributions, Funding, and Data Availability sections.
**Cite key in this project's `references.bib`:** `buildings2025risk_classification`
**Marked in `main.tex` as: Closest Competitor #2.**

## Method
Benchmarks 12 classification pipelines; traditional NLP (TF-IDF, Word2Vec), a Transformer model
(BERT), and GPT-4 under three prompting strategies (zero-shot, instruction-based, few-shot); on a
single task: assigning **already-written** risk statements to one of 11 predefined categories in a
Risk Breakdown Structure (RBS). This is risk **classification**, not risk **generation**: the
model is never asked to identify a risk from raw project documents, only to label a risk statement
someone else already wrote.

## Sample size
1,000 real risk statements drawn from 30 major U.S. transportation projects (20 states, USD 500M–2B
each), sourced from the ISMP database, mapped to an 11-category, 71-item RBS. Real, published,
large-N data; the biggest and most quantitative dataset of the five papers reviewed. 80/20
train/test split for the trained NLP baselines; the same held-out test set used for LLM prompting.

## Evaluation design
Standard classification metrics (accuracy, precision, recall, F1) against the real category
labels. Best performer: BERT+SVM (F1 = 0.86). GPT-4 few-shot: F1 = 0.81; GPT-4 instruction-based:
F1 = 0.82; GPT-4 zero-shot: F1 = 0.79. All GPT-4 runs used temperature = 0, max_tokens = 20 (i.e.,
forced to output a short category label only; not a full risk description, likelihood, impact,
or mitigation).

## Stated limitations (quoted/paraphrased directly from the paper's own "not without limitations" paragraph)
1. Only top-level (Level 1) RBS categories were tested; finer-grained sub-category classification,
   where categories overlap more, was not validated.
2. Evaluation used a static, curated dataset; not dynamic or fully unstructured real-time sources
   (contracts in progress, meeting minutes, social media).
3. No data-augmentation techniques were applied to underrepresented categories for the traditional
   NLP baselines, so the class-imbalance comparison may not be fully optimized on that side.
4. **Explicitly scoped to classification only**: the authors name generation as future work:
   "leveraging the generative capabilities of LLMs to not only identify emerging risks beyond fixed
   taxonomies but also to propose potential mitigation strategies" is listed as a direction for
   future research, not something this paper attempts.

## How this study differs
This is the strongest, most directly supported gap in the whole positioning table: this paper's
own stated future work, generating (not just classifying) risks and proposing mitigations, is
essentially this project's RQ1. `main.tex`'s claim that "classification and extraction are
materially easier tasks... they presuppose that the risks have already been identified" is
well-supported by this paper's own design (it starts from pre-existing risk statements) and its
own limitations paragraph (which frames generation as the natural next step, not something it
does). No changes recommended to how `main.tex` characterizes this paper.
