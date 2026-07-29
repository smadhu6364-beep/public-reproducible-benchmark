# Wen, H. et al. (2025) — "Using Large Language Models to Identify Project Risks for Sustainable Operations" (RiskGPT)

**Venue:** Proceedings of the 23rd CIB World Building Congress, 19–23 May 2025, Purdue University
(conference paper, not a journal article — confirmed correct in this project's `references.bib`,
which already lists it as `@inproceedings`, not `@article`).
**Source used:** Abstract and metadata confirmed directly from Purdue's e-Pubs page and PDF title
bar (primary source). The PDF itself (11 pages) would not render readable text through either the
fetch tool or the browser's built-in PDF viewer after repeated attempts — see "What's unverified"
below. Methodology detail beyond the abstract is drawn from a secondary web-search summary of the
paper, not independently read from the PDF body, and should be treated as lower-confidence than
the other four entries in this folder.
**Cite key in this project's `references.bib`:** `wen2025riskgpt`

## Method (abstract-confirmed)
Develops "RiskGPT," a custom GPT agent built on top of an underlying LLM via prompt engineering
(roleplaying, contextual prompting), knowledge augmentation, and fine-tuning. Per the abstract:
"developing a RiskGPT agent, fine-tuning it with prompt words, augmenting it with structural
knowledge, and evaluating its application on real projects." A secondary source describes the
design further: 10 assigned stakeholder roles (project manager, technical experts, financial
analysts, etc.) combined with a "Six Thinking Hats" framework to generate varied risk
perspectives — this detail is **not independently confirmed from the primary PDF** and should be
treated as reported-not-verified.

## Sample size
Abstract states evaluation via "a case study" on real projects — small-scale and exploratory. The
abstract's own wording — "preliminary results... demonstrate the potential benefits and
challenges" — signals this is a proof-of-concept demonstration, not a benchmark with a stated N.

## Evaluation design
Case-study demonstration, not a scored benchmark against ground truth. No recall/precision/
accuracy metrics are stated in the abstract.

## Stated limitations
Not confirmed — the Limitations/Discussion content is inside the PDF body, which could not be read
directly (see below). The abstract's own framing ("preliminary results," "potential... challenges")
is the closest thing to a self-stated limitation available from what was actually read.

## What's unverified
This is the weakest-sourced entry in this folder. Both `mcp__workspace__web_fetch` (tried twice,
including once via the ResearchGate mirror) and the Chrome browser's native PDF viewer (screenshot
timed out / rendered blank) failed to produce readable text from the 11-page PDF. The title bar
and URL were confirmed correct in Chrome, so this is genuinely the right paper — but the method
detail beyond the abstract (roles, "Six Thinking Hats," fine-tuning specifics) comes from a
web-search-engine-generated summary of the paper, not from text I read directly, and should be
re-verified before being stated as fact in the paper. If this level of confidence is not
acceptable for a "closest competitor" citation, the next step would be downloading the PDF to a
local machine (outside this session's tools) and re-extracting text there.

## How this study differs
Even taking the abstract at face value, RiskGPT is explicitly a single-agent, single-case-study,
"preliminary" demonstration — not a comparison across models, prompting strategies, or a corpus of
real published registers. This is consistent with `main.tex`'s existing characterization
("evaluated on a small set of case studies rather than a public benchmark"), which this review
supports at the confidence level available.
