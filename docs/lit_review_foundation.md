# Literature Review Foundation: LLM Risk Register Benchmark

**Status:** Working document, v1, 18 July 2026
**Purpose:** Seed the Related Work section, prove the research gap, and guide what we build.
**Rule:** Every entry below was found via live search and is verifiable. Before citing
any paper in the final manuscript, download the full text and read at least the
abstract, method, and limitations sections. **Never cite from a summary alone.**

## How this list is organized

Five themes. Our paper sits at the intersection of Themes 2, 3, and 4; that
intersection is empty, which is the gap.

- **Theme 1:** AI in project management (the broad field, establishes context)
- **Theme 2:** LLMs/ChatGPT for project risk management (the direct competitors)
- **Theme 3:** NLP/text mining for risk extraction (the pre-LLM baseline methods)
- **Theme 4:** LLM evaluation methodology (how to measure LLM output quality rigorously)
- **Theme 5:** Benchmarking and prompting strategies

---

## THEME 1: AI in Project Management (context setting, ~4-5 citations in final paper)

- **Salimimoghadam, S., Ghanbaripour, A.N., Tumpa, R.J., et al. (2025).** "The Rise
  of Artificial Intelligence in Project Management: A Systematic Literature Review of
  Current Opportunities, Enablers, and Barriers." *Buildings* (MDPI). Covers 2013–2024.
  *Use for:* growth trend of the field, adoption barriers.

- **(2025).** "Leveraging Artificial Intelligence in Project Management: A Systematic
  Review of Applications, Challenges, and Future Directions." *Computers* 14(2):66
  (MDPI). 97 studies, 2011–2024, PRISMA.
  *Use for:* AI applications concentrate in cost estimation, duration forecasting,
  risk assessment.

- **(2025).** "Mapping the AI Landscape in Project Management Context: A Systematic
  Literature Review." *Systems* 13(10):913 (MDPI). Scopus + WoS up to Nov 2024.
  *Use for:* theme mapping and explicitly identified research gaps.

- **(2026).** "AI-driven project management: Identifying use cases." *Procedia
  Computer Science* (ScienceDirect, S1877050926007301).
  **KEY GAP SOURCE:** heat map shows AI use cases concentrated in predictive
  analytics for time/cost/quality; generative AI functions ("generating and acting")
  notably underrepresented; academic research lags the technology.

- **(2025).** "Artificial intelligence tools for project management: A knowledge-based
  perspective." *Project Leadership and Society* / ScienceDirect (S2666721525000213).
  **KEY GAP SOURCE:** literature overhypes AI benefits, overlooks limitations; 70% of
  practitioners cite limited understanding of AI tools as the main adoption obstacle
  (citing Bodea et al. 2020).

- **(2024).** "Artificial intelligence in open innovation project management: A
  systematic literature review." ScienceDirect (S2199853124002397).
  *Use for:* only ~5 papers in their corpus discuss generative AI; quantifies how
  thin the genAI-in-PM literature is.

- **Karshiboev, A., et al. (2026).** "The Impact of AI and Data Analytics on Project
  Management Information Systems (PMIS)." Thematic review of 20 studies (2010–2025) on
  AI in Agile PM.
  *Use for:* fragmented understanding of AI effectiveness in Agile risk assessment;
  benefits claimed for sprint planning and early risk detection.

---

## THEME 2: LLMs/ChatGPT for Project Risk Management (direct competitors, read all fully)

- **(2025).** "Exploring Large Language Model AI tools in Construction Project Risk
  Assessment: ChatGPT Limitations in Risk Identification, Mitigation Strategies, and
  User Experience." *Journal of Construction Engineering and Management* (ASCE),
  Vol 151, No 9.
  **CLOSEST COMPETITOR #1.** Mixed-method, ChatGPT vs expert evaluation on
  infrastructure projects. Finding: strong on generic/checklist risks, weak on unique
  context-specific risks, the ones with the highest severity. Favorable UX; helps
  junior practitioners most.
  *Their limits we exploit:* single model (ChatGPT), construction only, no public
  reproducible corpus, no ground-truth registers.

- **Aladağ, H. (2023).** "Assessing the Accuracy of ChatGPT Use for Risk Management in
  Construction Projects." (MDPI journal; expert focus-group evaluation, GPT-3.5.)
  Finding: moderate risk-identification performance; broad generic coverage
  (political-legal, financial, environmental). Four KPIs incl. risk breakdown
  structure generation.
  *Limits:* GPT-3.5 only, non-anonymous focus groups, no document input (prompt-only),
  construction only.

- **(2023).** "Expert Evaluation of ChatGPT Performance for Risk Management Process
  based on ISO 31000 Standard." 33rd European Safety and Reliability Conference
  (ESREL), Southampton.
  Finding: best performance on mitigation-strategy suggestions; Likert-based
  practitioner scoring (mean f-pn 0.3997 = "high").
  *Limits:* user-testing design, no ground truth, single model.

- **(2024).** "Can ChatGPT exceed humans in construction project risk management?"
  *Engineering, Construction and Architectural Management* (Emerald), Vol 31, No 13.
  GPT-4 vs human experts on a CPRM test with anonymous blind peer review. Explicitly
  criticizes prior work for non-anonymous evaluation bias.
  *Use for:* justifying our blinded rating protocol.

- **Wen, H., et al. (2025).** "Using Large Language Models to Identify Project Risks
  for Sustainable Operations." (June 2025.)
  Develops "RiskGPT" agent: prompt tuning + structural knowledge augmentation,
  case-study evaluation on real construction projects.
  Findings: generalization tendency, fabrication issues, needs validation checks and
  human-AI workflows.
  *Limits:* single fine-tuned agent, case study (not benchmark), no cross-model
  comparison.

- **(2023, arXiv 2309.12132; later journal version).** "Automating construction
  contract review using knowledge graph-enhanced large language models." GraphRAG +
  Nested Contract Knowledge Graph for contract risk identification on EPC contracts.
  *Use for:* retrieval-augmented alternative approach; shows tuning-free LLM+KG beats
  baselines on contract risk. Adjacent task (contract risk, not full register).

- **Barcaui, A. & Monat, A. (2023).** "Who is better in project planning? Generative
  artificial intelligence or project managers?" (Cited repeatedly across Theme 2
  papers as an early genAI-vs-human PM comparison; **verify exact venue when
  downloading.**)

---

## THEME 3: Pre-LLM NLP/Text Mining for Risk Extraction (baseline lineage, ~3 citations)

- **(2025).** "Large Language Models for Construction Risk Classification: A
  Comparative Study." *Buildings* 15(18):3379 (MDPI).
  **CLOSEST COMPETITOR #2.** Benchmarks NLP vs LLM techniques (incl. prompt
  engineering variants) for classifying risk items into categories.
  *Critical difference from us:* they **classify** already-identified risk items; we
  **generate** full registers from raw project documents and score against human
  ground truth. Classification ≠ generation. State this distinction explicitly in
  Related Work.

- **(2025).** "A systematic review of text mining analytics for supply chain risk
  management using online data." ScienceDirect (S2949863525000676). 33 studies.
  *Use for:* text-mining lineage, data-reliability trade-offs.

- **(2026).** "Text mining and natural language processing in construction research: a
  scientometric analysis and qualitative review." *Frontiers in Built Environment*.
  *Use for:* LLMs now the de facto paradigm for construction text tasks; notes
  comparative evaluation of NLP methods remains limited.

---

## THEME 4: LLM Evaluation Methodology (defends our evaluation design, ~4 citations)

- **(2024, arXiv 2412.05579).** "LLMs-as-Judges: A Comprehensive Survey on LLM-based
  Evaluation Methods."
  *Use for:* framework and known limitations of LLM-as-judge; justifies why Method C
  is supplementary only.

- **(2025, arXiv 2503.05061).** "No Free Labels: Limitations of LLM-as-a-Judge Without
  Human Grounding."
  Finding: judges fail on questions they can't answer themselves; human reference
  answers improve agreement and reduce self-preference bias.
  *Use for:* why we anchor on ground-truth registers + human raters, with LLM-judge
  only correlated against them.

- **(2025).** "Limitations of the LLM-as-a-Judge Approach for Evaluating LLM Outputs
  in Expert Knowledge Tasks." Proceedings of ACM IUI 2025 (also arXiv 2410.20266).
  *Use for:* expert-domain judging is exactly our setting (risk management = expert
  knowledge).

- **Zheng et al. (2023).** "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena."
  (Foundational; cited across Theme 4 papers for positional bias, verbosity bias,
  self-enhancement bias. **Verify NeurIPS 2023 version when downloading.**)

---

## THEME 5: Benchmarking & Prompting (~2-3 citations)

- **Kappa/inter-rater methodology:** cite **Fleiss (1971)** for Fleiss' kappa and
  **Landis & Koch (1977)** for interpretation bands, standard, uncontroversial,
  needed for Method B.
- **Prompting strategies:** **Brown et al. (2020)** for few-shot in-context learning;
  **Wei et al. (2022)** for chain-of-thought. Foundational, **verify exact citations
  from the original arXiv/NeurIPS versions.**
- **Thakur et al. (2024)** (cited in Theme 4 sources): argues Cohen's kappa over
  percent agreement for judge-human alignment: directly supports our metric choice.

---

## GAP ANALYSIS: what the literature does NOT do (our paper's justification)

| # | Gap in existing work | Evidence | Our answer |
|---|----------------------|----------|------------|
| G1 | Generative AI is one of the least-studied AI functions in PM research; field concentrated on predictive analytics for time/cost/quality | Theme 1: #4, #6 | We study generation directly (full risk registers) |
| G2 | Existing LLM-risk studies are single-model (almost all ChatGPT-only) | #8, #9, #10, #12 | 3-model comparison incl. open-source (RQ2) |
| G3 | No study evaluates against real published human risk registers as ground truth; evaluations are expert-opinion-only or author-judged | #8–#12 all use expert panels or case studies | Method A: ground-truth matching with recall/precision (RQ1) |
| G4 | Almost everything is construction-sector; no cross-sector public corpus | #8, #9, #11, #12, #15 | World Bank + UK IPA corpus spans sectors |
| G5 | No public, reproducible benchmark exists (no shared corpus, prompts, or code) | None of #8–#15 release a benchmark | We release corpus manifest, prompts, code |
| G6 | Known LLM weakness (generic risks strong, context-specific risks weak) has never been quantified per risk category | #8 observes it qualitatively | RQ3 failure-mode analysis, per-category recall |
| G7 | Prior evaluations criticized for non-anonymous/non-blind rating bias | #11 explicitly | Blinded rating protocol, Fleiss' kappa reported |
| G8 | Classification of risks ≠ generation of registers; the generation task is unbenchmarked | #15 does classification only | We benchmark generation end-to-end |

**One-sentence gap statement for the paper (draft):**
> "While recent studies have assessed ChatGPT's ability to discuss project risks under
> expert evaluation, no work has benchmarked multiple LLMs on end-to-end risk register
> generation from real project documents against published human-authored registers,
> leaving both the accuracy and the systematic failure modes of this capability
> unquantified."

## Honest threats to our novelty (do not ignore these)

- The ASCE 2025 paper (#8) and RiskGPT (#12) are close. Our defense is **G2+G3+G5**:
  multi-model, ground-truth-based, public benchmark. If a paper appears in the next 6
  months doing exactly that, our contribution shrinks; monitor Google Scholar alerts
  for "LLM risk register", "LLM risk identification benchmark" monthly.
- Reviewer will ask: "Why not fine-tune?" Answer in paper: we benchmark off-the-shelf
  capability because that is how practitioners actually use these tools (supported by
  #5: limited understanding is the adoption barrier; nobody is fine-tuning in a PMO).

## WHAT WAS DONE TODAY (progress log, keep updating every session)

- **[18 Jul 2026]** Ran structured literature search across 4 query families (LLM+PM
  risk, ChatGPT risk evaluation, NLP risk extraction, LLM-as-judge). Compiled 24
  verified reference candidates across 5 themes. Built gap table G1–G8 mapped to
  RQ1–RQ3. Drafted the paper's gap statement.

## LEARNING NOTES (for Madhu: the "why" behind each move)

- A Related Work section is an argument, not a list. Themes 1–3 say "here is what
  exists," Theme 4 says "here is how to measure properly," and the gap table says
  "here is the hole we fill." Reviewers score exactly this structure.
- The most dangerous papers are the closest ones (#8, #12, #15). You never hide them:
  you cite them prominently and state precisely how you differ. Hiding a close
  competitor a reviewer knows about = instant rejection.
- Ground truth beats opinion. Every prior study used expert panels; panels are
  subjective and non-reproducible. Our recall/precision against published registers is
  the methodological upgrade: that is the paper's spine.
- 24 candidates → ~20–25 final citations is correct sizing for a 6–8 page IEEE
  conference paper (roughly: 5 context, 7 competitors, 3 baselines, 4 evaluation, 3
  methods/foundations, plus data sources).

## NEXT ACTIONS (in order)

1. **[Madhu, this week: still the gate]** Pull 5 World Bank PADs + 5 UK IPA docs;
   confirm risk registers are extractable. Nothing else proceeds until this passes.
2. **[Kruthik]** Download full texts of #8, #9, #11, #12, #15 (the five must-reads).
   Write a half-page summary of each: method, sample size, evaluation design, stated
   limitations. Deadline: 2 weeks.
3. **[Either]** Set up shared Zotero library + Google Scholar alerts ("LLM risk
   register", "large language model risk identification project").
4. **[Done]** This file saved into the repo as
   `docs/lit_review_foundation.md`, and `paper/references.bib` seeded with entries for
   the confirmed papers (leave TODO fields where the exact venue/pages need
   verification from full text).
5. **[Both]** After the 5 must-reads: 1-hour call to pressure-test the gap table. If
   any gap is weaker than claimed here, revise before writing a word of the paper.
