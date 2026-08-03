# Hand-verification notes on the 2026-07-20 corpus_audit_report.md run

Not part of `src/audit_corpus.py`'s own output (that stays purely mechanical
and gets overwritten on every re-run) - this is a one-off, dated human review
of the 4 non-PASS findings from the run recorded in
`results/corpus_audit_report.md`, written after
manually re-checking each one against the source PDF / processed text /
ground truth JSON. Report-only, same as the script: nothing below was
auto-fixed. Treat this as a starting point for the fix decision the task
asked for, not as the fix itself.

## P-UK-PadeswoodCCUS - WARN on check 1 - likely a false positive

The scanner found "3.4 Risk Appraisal" matching on page 9, one page before
the declared range (10-11). Checked page 9 directly: it's a footnote -
"The value for money impact of a delay to Padeswood COD beyond this is
summarised in '3.4 Risk Appraisal'" - a forward cross-reference to the
section title, not a second occurrence of the actual section. No action
needed; this is exactly the kind of ambiguous case WARN exists for.

## P-MAR-SecondIdentityTargetingSocialProtection - FAIL on check 2 - false positive

Flagged phrase "the first Identity and Targeting for Social Protection" and
code "P155198" both come from R01's mitigation text, which legitimately
names the predecessor World Bank project (P155198, closed) that this one
builds on. That predecessor project is discussed extensively throughout the
document's ordinary background/lessons-learned narrative (13+ occurrences
checked via grep, e.g. lines 349, 759, 1302, 1354, 1544...) for reasons
having nothing to do with the risk register - it's simply the name of a real,
specific prior project. This is a known limitation of a verbatim-phrase leak
check: a proper-noun/project-name reference that recurs legitimately in
background context will always trigger it, even though it isn't
risk-register content leaking back in. No fix needed to the corpus; if
anything, a future version of the leak check could exclude phrases that are
just a project name + ID pattern.

## P-PER-ArequipaColca - FAIL on check 2 - likely a REAL, previously-missed bug

R03's description states: "Combined fiduciary risk with GORE Arequipa is
Substantial, reflecting the entity's lack of prior experience with World
Bank or other MDB-financed operations in both financial management and
procurement." The processed text (Appraisal Summary, Procurement
sub-section, para 65) states: "A procurement capacity assessment was
conducted to evaluate the existing systems... The assessment revealed a lack
of prior experience with World Bank or other MDB-financed operations in
procurement." This is a near-verbatim restatement of the exact same rated
finding (lack of prior WB/MDB procurement experience -> fiduciary risk) that
R03 scores as Substantial. corpus_manifest.csv's existing note for this row
already flags "p30-33 appraisal summary risk discussion (incidental)" as a
known, already-reviewed overlap - but that classification predates this
session's stricter standard (established while fixing P-KHM, P-SLE, P-BGD):
substantive restatement of a *scored* risk's finding is leakage and should be
excised, not left in as "incidental." Recommend re-reviewing this row under
that same standard, the same way KHM/SLE/BGD were fixed.

## P-UGA-IntegratedWaterMgmtDev - FAIL on both checks - CONFIRMED real, well-evidenced

Real PDF page 78 (Appraisal Summary, Financial Management/Procurement
annex - well outside the declared excision range of 27-28) contains two
separate near-verbatim restatements of scored register content:

1. Para 18 on page 78 opens "Key risks envisaged under the current Project
   are the following: (a) ministry internal audit review reports are not
   shared regularly with the World Bank... (b) the IFMS has not been fully
   operationalized..." - this is what triggered check 1's heading-pattern
   match on page 78 (the phrase "Key risks" is real body prose here, not a
   formal section heading, but the content itself substantively echoes R03's
   fiduciary/FM risk).
2. Later on the same page: "The IWMDP will benefit from the capacity and
   knowledge built as well as the lessons learned and mechanisms put in
   place under the WMDP" - near-identical to R03's own mitigation text:
   "IWMDP will benefit from the lessons learned and mechanisms put in place
   under the predecessor project (WMDP)."

corpus_manifest.csv's existing note for this row already documents this
exact page ("p78-p79 Financial Management annex restates the
ministry-internal-audit-review risk item almost verbatim") but classifies it
as "incidental... not part of the primary register, not separately
excised" - the same now-outdated classification standard as the Peru
finding above, and the same failure pattern already fixed for KHM/SLE/BGD
this session (a scored risk's substance restated outside the excision
range). Of the four findings in this run, this is the most confidently real
one - two independent restatements on the same page, one of which is a
near-verbatim match of the ground truth's own mitigation sentence.
