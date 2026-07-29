# Closest-competitor papers — full-text verification (2026-07-29)

Five files, one per paper, each covering method / sample size / evaluation design / stated
limitations, and checking that against how `paper/main.tex` currently describes it. Source
confidence is stated at the top of each file — four of five were read in substantial full text
from the real publisher/repository page; one (RiskGPT) is abstract-only, flagged clearly.

| # | Paper | Cite key | Source confidence |
|---|---|---|---|
| 1 | Aladağ (2023), Sustainability | `aladag2023assessing_chatgpt` | Full text, Sections 1–4 (Section 5 unreachable) |
| 2 | Nyqvist et al. (2024), ECAM | `ecam2024chatgpt_exceed_humans` | Full text, all sections incl. Limitations §5.3 verbatim |
| 3 | Martin et al. (2025), ASCE JCEM — Closest Competitor #1 | `asce2025exploring_chatgpt_risk` | Full text, Abstract/Method/Conclusion (Results/Discussion skimmed only) |
| 4 | Wen et al. (2025), RiskGPT, CIB Congress | `wen2025riskgpt` | Abstract only — PDF body unreadable via available tools |
| 5 | Erfani/Khanjar et al. (2025), Buildings — Closest Competitor #2 | `buildings2025risk_classification` | Full text, all sections incl. Conclusions verbatim |

## Bottom line: are `main.tex`'s claims about these 5 papers accurate?

**Yes, on the whole.** Every row of the Positioning gap table (`tab:gap`) and both paragraphs in
"LLMs for Project Risk Management" / "Risk Classification and Text Mining vs. Generation" check
out against what these papers actually say. In particular:

- **"Single-model, almost always ChatGPT"** — confirmed for all 5, no exceptions. Two of them
  (Martin/ASCE and Erfani/Buildings) explicitly name "test more models" as their own future work.
- **"Classification is materially easier than generation"** — this is not just this project's
  framing; Erfani/Buildings' own limitations paragraph says the same thing in their own words and
  names risk generation + mitigation as future work — i.e., exactly this project's RQ1.
- **"Evaluated on a small set of case studies rather than a public benchmark" (RiskGPT)** —
  confirmed by the abstract alone ("a case study," "preliminary results").

## Two real issues found, worth a look before submission

1. **The gap table's "Non-blind rating designs criticized in prior work" row risks overclaiming.**
   Nyqvist et al. (2024) is explicitly, proudly a blind design — their own paper calls itself "a
   pioneering blind-review study" with 19 anonymous peer reviewers. If a reviewer who knows this
   paper reads the gap table as claiming all five closest competitors use non-blind designs,
   that's a factual problem for at least one of them. **Recommend:** narrow that row's wording —
   e.g., "no formal inter-rater agreement statistic (kappa) reported," which is true even for
   Nyqvist's blind design — or add a one-line footnote carving out Nyqvist's paper by name. See
   `02_nyqvist2024_ecam.md` for the full note.

2. **"Related studies report similar patterns" (Aladağ + Nyqvist, line ~204) slightly overstates
   agreement between the two.** Aladağ's headline finding is "ChatGPT is moderate/mediocre
   overall." Nyqvist's headline finding is "ChatGPT quantitatively *beats* humans (8.6 vs. 5.7),
   but lacks practical specificity." Both papers do share a real sub-finding — strong on generic
   output, weak on specific/practical output — which is presumably what "similar patterns" is
   meant to point at. But as written, a careful reader could take "similar patterns" to mean both
   studies reached the same overall verdict on ChatGPT, which they didn't. **Recommend:** tighten
   the sentence to name the shared sub-finding explicitly (generic-strong / specific-weak) rather
   than leaving "similar patterns" open to the stronger, inaccurate reading.

Neither of these is a fabrication or a wrong citation — both are precision issues in how two
findings get summarized in one shared sentence/row. Worth a two-line fix each, not a rewrite.

## What's still genuinely unverified

- Aladağ's Section 5 (Discussion/Limitations) — the fetch cut off before this section; the
  "stated limitations" in `01_aladag2023_sustainability.md` are inferred from the methodology,
  not quoted from the paper's own limitations list.
- RiskGPT's full method/limitations beyond the abstract — the PDF would not render text through
  either the fetch tool or the browser's PDF viewer after multiple real attempts (not skipped
  without trying). If exact quotes from this paper are needed for the submitted paper, this one
  needs a manual download-and-read on a real machine.
- Martin et al.'s Results/Discussion sections (the specific per-category findings, as opposed to
  the method and conclusion, which are both fully read) — not read in detail due to time; the
  method/sample-size/limitations facts above are still solid, this only affects citing specific
  numeric findings from that paper's Results section.
