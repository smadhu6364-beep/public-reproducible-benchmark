"""audit_corpus.py - independent, rerunnable leakage / page-range audit.

Every excision bug found in this project so far (the systemic SORT-table
under-excision across 8 WB documents, the Uganda over-excision, HyNet's
2-page draft offset) was caught by manually opening a source document and
checking page-by-page against corpus_manifest.csv's recorded ranges - never
by trusting the recorded range itself. That was always done ad hoc, one
document at a time. This script makes that check systematic and rerunnable
across every included project.

REPORT ONLY. This script never modifies corpus_manifest.csv, any
data/ground_truth/*.json file, or any data/processed/*.txt file. If it finds
a discrepancy, it prints/writes a flagged finding for a human to act on - the
same way the Uganda and HyNet corrections were each a deliberate, written,
one-off fix, not an automated one.

Two independent checks, run for every corpus_manifest.csv row with
inclusion_status=included:

  1. Page-range re-verification (PDF-sourced projects only). Opens the real
     PDF in data/raw/<project_id>/ and searches page-by-page for the actual
     section-heading text (e.g. "KEY RISKS", a SORT-table signature, or for
     UK docs the specific numbered headings like "2.5 Identify high level
     potential risks") - independently re-deriving where the risk-bearing
     section(s) start and end, then comparing that against what
     corpus_manifest.csv's sort_pages / section_v_pages columns claim.
     P-UK-FreeBreakfastClubs is HTML-only (no PDF, no pagination) and is
     skipped here; it is handled entirely under check 2.

  2. Leak check (all included projects, regardless of source type). Loads
     each project's ground truth JSON, pulls every risk's description and
     mitigation text (plus any distinctive short codes mentioned in it, e.g.
     HyNet's "T1SR1"), and confirms none of it appears - verbatim, in
     sliding 8-word windows - in the corresponding data/processed/*.txt file
     that models are actually prompted with. For P-UK-FreeBreakfastClubs
     specifically, this also re-fetches the live HTML and confirms the
     scored risk-bullet text and the (deliberately unexcised) "Risk and
     issue management" process section both still match what
     data/processed/P-UK-FreeBreakfastClubs.txt and the ground truth file
     currently expect.

Heuristic limits (read before trusting a PASS): the WB heading/SORT-table
detector is regex-based and was tuned against the heading conventions
observed in this corpus ("V. KEY RISKS", "VI. KEY RISKS", "V. RISKS", and a
SORT-table content signature). It can miss an unusual heading (false
PASS-by-silence, surfaced as an "unverified declared page" WARN) or flag an
incidental cross-reference as a false leak candidate (surfaced as WARN, not
FAIL, unless the found page is more than 2 pages from anything declared).
FAIL is reserved for either a confirmed verbatim leak (check 2) or a heading
match clearly outside the declared range with no declared page anywhere near
it (check 1). Every WARN/FAIL prints its exact evidence so a human can judge
it in seconds rather than re-deriving it from scratch.

Usage:
  python src/audit_corpus.py                 # audit every included project
  python src/audit_corpus.py --project-id P-SRB-CompetitivenessJobs
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import _parse_page_ranges  # reuse the exact page-range parsing extract.py itself uses

DEFAULT_MANIFEST = Path("data/corpus_manifest.csv")
DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_GT_DIR = Path("data/ground_truth")
DEFAULT_REPORT_PATH = Path("results/corpus_audit_report.md")

HTML_ONLY_PROJECTS = {"P-UK-FreeBreakfastClubs"}
FREE_BREAKFAST_CLUBS_URL = (
    "https://www.gov.uk/api/content/government/publications/"
    "free-breakfast-clubs-summary-business-case/"
    "13-march-2026-free-breakfast-clubs-summary-business-case"
)

# --- WB heading / SORT-table detection -------------------------------------

KEY_RISKS_HEADING_RE = re.compile(
    r"(?m)^\s*(?:[IVXLC]{1,5}\.?\s+)?KEY\s+RISKS\b", re.IGNORECASE
)
RISKS_ONLY_HEADING_RE = re.compile(
    r"(?m)^\s*[IVXLC]{1,5}\.\s*RISKS\s*$", re.IGNORECASE
)
SORT_WORD_RE = re.compile(r"\bSORT\b", re.IGNORECASE)
SORT_CATEGORY_HINTS = [
    "political and governance",
    "macroeconomic",
    "sector strategies",
    "technical design",
    "institutional capacity",
    "fiduciary",
    "environment and social",
    "stakeholders",
    "overall",
]

# --- UK PDF docs: known section headings ------------------------------------
# Hand-verified against the real PDFs 2026-07-19. Searched
# here by literal heading text, independently of any previously-recorded
# page number, per this task's brief.
UK_HEADINGS: dict[str, list[tuple[str, re.Pattern]]] = {
    "P-UK-HyNetCCUSCluster": [
        ("1.6 Deliverability and risks", re.compile(r"1\.6\s+Deliverability and risks", re.IGNORECASE)),
        ("2.5 Identify high level potential risks", re.compile(r"2\.5\s+Identify high level potential risks", re.IGNORECASE)),
        ("3.7 Risk Appraisal", re.compile(r"3\.7\s+Risk Appraisal", re.IGNORECASE)),
        ("4.2.4 Cluster-level commercial risk assessment", re.compile(r"4\.2\.4\s+Cluster-level commercial risk assessment", re.IGNORECASE)),
        ("5.7 Financial risks", re.compile(r"5\.7\s+Financial risks", re.IGNORECASE)),
    ],
    "P-UK-PadeswoodCCUS": [
        ("3.4 Risk Appraisal", re.compile(r"3\.4\s+Risk Appraisal", re.IGNORECASE)),
        ("5.4 Financial Risks", re.compile(r"5\.4\s+Financial Risks", re.IGNORECASE)),
    ],
}

# --- distinctive short-code detector (e.g. "T1SR1") -------------------------
# Deliberately requires the digit to be inside the matched token itself
# (checked in Python below, not via regex lookahead - an earlier lookahead
# version scanned past the token into unrelated later text and produced
# false positives on plain acronyms like "HMG"/"FID"/"COD").
DISTINCTIVE_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]{3,7}\b")
_RISK_ID_RE = re.compile(r"^R\d{1,3}$")

# --- table-of-contents page filter -------------------------------------
# A ToC line looks like "4.2.4 Cluster-level commercial risk assessment .... 30"
# - dot leaders followed by a page number. Without this filter, a ToC page
# that lists every section heading in one place reads as a false match for
# ALL of them simultaneously.
TOC_LEADER_RE = re.compile(r"\.{4,}\s*\d{1,4}\s*$", re.MULTILINE)


def is_toc_page(text: str) -> bool:
    return len(TOC_LEADER_RE.findall(text)) >= 3


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def load_included_rows(manifest_path: Path) -> list[dict]:
    with open(manifest_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("inclusion_status") == "included"]


def find_project_pdf(project_id: str, raw_dir: Path) -> Path | None:
    project_dir = raw_dir / project_id
    if not project_dir.is_dir():
        return None
    pdfs = sorted(project_dir.glob("*.pdf"))
    return pdfs[0] if len(pdfs) == 1 else (pdfs[0] if pdfs else None)


def extract_raw_pages(pdf_path: Path) -> list[str]:
    """Return raw per-page text, index i == PDF page i+1. Deliberately NOT
    reusing extract.py's cleaned-page pipeline - this needs to be an
    independent re-derivation, not a second read of the same cleaned text.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed. Run: pip install -r requirements.txt")
    with fitz.open(pdf_path) as doc:
        return [page.get_text("text") for page in doc]


def scan_wb_headings(pages: list[str]) -> dict[str, list[int]]:
    key_risks_pages: list[int] = []
    hint_hit_pages: dict[int, int] = {}
    sort_anchor_pages: set[int] = set()
    for i, text in enumerate(pages):
        if is_toc_page(text):
            continue
        page_no = i + 1
        if KEY_RISKS_HEADING_RE.search(text) or RISKS_ONLY_HEADING_RE.search(text):
            key_risks_pages.append(page_no)
        hint_hit_pages[page_no] = sum(1 for h in SORT_CATEGORY_HINTS if h in text.lower())
        if SORT_WORD_RE.search(text):
            sort_anchor_pages.add(page_no)

    # A multi-page SORT table's header ("SORT") often only appears on its
    # first page - continuation pages (e.g. categories 2-10 of a 10-row
    # table split across two pages) won't repeat it (see P-BFA: page 8 has
    # "SORT" + category 1 only, page 9 has categories 2-10 with no "SORT"
    # literal at all). But requiring >=3 hints with NO proximity-to-"SORT"
    # requirement at all was too loose - appraisal-summary prose elsewhere
    # in a PAD can discuss 3+ of the same category names narratively without
    # being the actual table. Require both: >=3 hits AND within 1 page of an
    # actual "SORT" occurrence somewhere in the document.
    sort_table_pages = [
        p for p, hits in hint_hit_pages.items()
        if hits >= 3 and any(abs(p - a) <= 1 for a in sort_anchor_pages)
    ]
    return {"key_risks_pages": key_risks_pages, "sort_table_pages": sorted(sort_table_pages)}


def scan_uk_headings(pages: list[str], project_id: str) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for label, pattern in UK_HEADINGS.get(project_id, []):
        hits = [i + 1 for i, text in enumerate(pages) if not is_toc_page(text) and pattern.search(text)]
        result[label] = hits
    return result


def _contiguous_blocks(pages: set[int]) -> list[list[int]]:
    blocks: list[list[int]] = []
    for p in sorted(pages):
        if blocks and p == blocks[-1][-1] + 1:
            blocks[-1].append(p)
        else:
            blocks.append([p])
    return blocks


def classify_page_range(declared: set[int], found: set[int]) -> tuple[str, dict]:
    leaked = sorted(found - declared)
    # A declared page only counts as "unverified" if its WHOLE contiguous
    # block (e.g. a 2-page section 13-14) has zero hits - a real section
    # heading typically only appears on the first page of a multi-page
    # block, so page 14 having no hit while page 13 does is expected, not a
    # miss.
    unverified: list[int] = []
    for block in _contiguous_blocks(declared):
        if not any(p in found for p in block):
            unverified.extend(block)
    details = {"leaked_pages": leaked, "unverified_declared_pages": unverified}
    if not leaked and not unverified:
        return "PASS", details
    if leaked:
        if not declared:
            return "FAIL", details
        far = [p for p in leaked if min(abs(p - d) for d in declared) > 2]
        if far:
            details["far_leaked_pages"] = far
            return "FAIL", details
        return "WARN", details
    return "WARN", details


def audit_page_ranges(row: dict, raw_dir: Path) -> dict:
    project_id = row["project_id"]
    pdf_path = find_project_pdf(project_id, raw_dir)
    if pdf_path is None:
        return {"status": "WARN", "detail": f"no single PDF found under {raw_dir / project_id}/"}

    pages = extract_raw_pages(pdf_path)
    declared = _parse_page_ranges(row.get("sort_pages")) | _parse_page_ranges(row.get("section_v_pages"))

    is_uk = project_id in UK_HEADINGS
    if is_uk:
        found_by_label = scan_uk_headings(pages, project_id)
        found = set()
        for hits in found_by_label.values():
            found.update(hits)
        scan_detail = found_by_label
    else:
        wb = scan_wb_headings(pages)
        found = set(wb["key_risks_pages"]) | set(wb["sort_table_pages"])
        scan_detail = wb

    status, details = classify_page_range(declared, found)
    return {
        "status": status,
        "total_pages": len(pages),
        "declared_pages": sorted(declared),
        "found_pages": sorted(found),
        "scan_detail": scan_detail,
        **details,
    }


def extract_leak_candidates(risk: dict) -> list[str]:
    """8-word sliding-window candidate phrases from a risk's description and
    mitigation, citation brackets like '[Financial Case Sec 5.7...]' stripped
    first so a section-name citation doesn't get treated as source text.
    """
    candidates: list[str] = []
    for field in ("description", "mitigation"):
        text = risk.get(field) or ""
        text = re.sub(r"\[.*?\]", "", text)
        for sentence in re.split(r"(?<=[.;])\s+", text):
            words = sentence.split()
            if len(words) < 8:
                continue
            for i in range(0, len(words) - 7, 4):
                candidates.append(" ".join(words[i : i + 8]))
    return candidates


def extract_distinctive_codes(risk: dict, own_risk_ids: set[str]) -> list[str]:
    codes: set[str] = set()
    for field in ("description", "mitigation"):
        text = risk.get(field) or ""
        for m in DISTINCTIVE_CODE_RE.finditer(text):
            token = m.group(0)
            if token in own_risk_ids or _RISK_ID_RE.match(token):
                continue
            if not any(c.isdigit() for c in token):
                continue  # require the digit inside the token itself - filters plain acronyms (HMG, FID, COD, DESNZ, ...)
            codes.add(token)
    return sorted(codes)


def leak_check(gt: dict, processed_text: str) -> dict:
    processed_norm = norm(processed_text)
    own_risk_ids = {r.get("risk_id", "") for r in gt.get("risks", [])}
    findings = []
    for risk in gt.get("risks", []):
        for phrase in extract_leak_candidates(risk):
            if norm(phrase) and norm(phrase) in processed_norm:
                findings.append({"risk_id": risk.get("risk_id"), "type": "verbatim_phrase", "text": phrase})
        for code in extract_distinctive_codes(risk, own_risk_ids):
            if re.search(rf"\b{re.escape(code)}\b", processed_text):
                findings.append({"risk_id": risk.get("risk_id"), "type": "distinctive_code", "text": code})
    status = "FAIL" if findings else "PASS"
    return {"status": status, "findings": findings}


def audit_free_breakfast_clubs_html() -> dict:
    """Special case per the task brief: no PDF/pagination exists, so check 1
    is skipped and folded into an HTML-specific re-fetch here instead.
    """
    try:
        with urllib.request.urlopen(FREE_BREAKFAST_CLUBS_URL, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        body = data["details"]["body"]
    except Exception as exc:  # network unavailable, page moved, etc.
        return {"status": "WARN", "detail": f"could not re-fetch live HTML: {exc}"}

    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text)
    text_norm = text.lower()

    expected_bullets = [
        "lower value for money compared to",
        "delivery risks around staffing and food costs",
        "uncertainty in labour market benefits",
    ]
    missing_bullets = [b for b in expected_bullets if b not in text_norm]

    processed_path = DEFAULT_PROCESSED_DIR / "P-UK-FreeBreakfastClubs.txt"
    processed_text = processed_path.read_text(encoding="utf-8") if processed_path.exists() else ""
    processed_norm = norm(processed_text)

    leaked_bullets = [b for b in expected_bullets if b in processed_norm]
    marker_present = "excised" in processed_norm and "ground-truth register" in processed_norm

    findings = []
    if missing_bullets:
        findings.append({"type": "live_html_drifted", "text": missing_bullets})
    if leaked_bullets:
        findings.append({"type": "risk_bullets_leaked_into_processed", "text": leaked_bullets})
    if not marker_present:
        findings.append({"type": "excision_marker_missing", "text": "expected bracketed excision marker not found in processed text"})

    status = "FAIL" if (leaked_bullets or not marker_present) else ("WARN" if missing_bullets else "PASS")
    return {"status": status, "findings": findings}


def audit_project(row: dict, raw_dir: Path, processed_dir: Path, gt_dir: Path) -> dict:
    project_id = row["project_id"]
    result: dict = {"project_id": project_id}

    gt_path = gt_dir / f"{project_id}.json"
    processed_path = processed_dir / f"{project_id}.txt"
    if not gt_path.exists():
        result["check2"] = {"status": "FAIL", "findings": [{"type": "missing_ground_truth_file", "text": str(gt_path)}]}
    elif not processed_path.exists():
        result["check2"] = {"status": "FAIL", "findings": [{"type": "missing_processed_file", "text": str(processed_path)}]}
    else:
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        processed_text = processed_path.read_text(encoding="utf-8")
        result["check2"] = leak_check(gt, processed_text)

    if project_id in HTML_ONLY_PROJECTS:
        result["check1"] = {"status": "SKIPPED", "detail": "HTML-only publication, no PDF/pagination - see check2b"}
        result["check2b_html"] = audit_free_breakfast_clubs_html()
    else:
        try:
            result["check1"] = audit_page_ranges(row, raw_dir)
        except Exception as exc:
            result["check1"] = {"status": "FAIL", "detail": f"error during page-range audit: {exc}"}

    statuses = [result["check1"]["status"]]
    if result["check1"]["status"] != "SKIPPED":
        pass
    statuses.append(result["check2"]["status"])
    if "check2b_html" in result:
        statuses.append(result["check2b_html"]["status"])
    real_statuses = [s for s in statuses if s != "SKIPPED"]
    if "FAIL" in real_statuses:
        overall = "FAIL"
    elif "WARN" in real_statuses:
        overall = "WARN"
    else:
        overall = "PASS"
    result["overall"] = overall
    return result


def format_report(results: list[dict]) -> str:
    lines = ["# Corpus audit report", ""]
    lines.append("Report-only. No manifest, ground-truth, or processed-text file was modified by this run.")
    lines.append("")
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for r in results:
        counts[r["overall"]] += 1
    lines.append(f"**Summary: {counts['PASS']} PASS / {counts['WARN']} WARN / {counts['FAIL']} FAIL** (of {len(results)} included projects)")
    lines.append("")
    for r in sorted(results, key=lambda r: (r["overall"] != "FAIL", r["overall"] != "WARN", r["project_id"])):
        lines.append(f"## {r['project_id']} - {r['overall']}")
        c1 = r["check1"]
        if c1["status"] == "SKIPPED":
            lines.append(f"- Check 1 (page-range): SKIPPED - {c1['detail']}")
        elif "detail" in c1 and c1["status"] in ("FAIL", "WARN") and "declared_pages" not in c1:
            lines.append(f"- Check 1 (page-range): {c1['status']} - {c1['detail']}")
        else:
            lines.append(
                f"- Check 1 (page-range): {c1['status']} - declared={c1.get('declared_pages')} "
                f"found={c1.get('found_pages')} total_pages={c1.get('total_pages')}"
            )
            if c1.get("leaked_pages"):
                lines.append(f"  - pages with a heading/SORT match OUTSIDE the declared excision range: {c1['leaked_pages']}")
            if c1.get("unverified_declared_pages"):
                lines.append(f"  - declared pages with NO heading/SORT match found: {c1['unverified_declared_pages']}")
            if c1.get("scan_detail"):
                lines.append(f"  - raw scan detail: {c1['scan_detail']}")
        c2 = r["check2"]
        lines.append(f"- Check 2 (leak check): {c2['status']}")
        for f in c2.get("findings", []):
            lines.append(f"  - [{f['type']}] risk={f.get('risk_id')}: `{f['text']}`")
        if "check2b_html" in r:
            c2b = r["check2b_html"]
            lines.append(f"- Check 2b (live HTML re-fetch, FreeBreakfastClubs only): {c2b['status']}")
            for f in c2b.get("findings", []):
                lines.append(f"  - [{f['type']}]: {f['text']}")
            if "detail" in c2b:
                lines.append(f"  - {c2b['detail']}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-id", help="Audit a single project instead of all included projects.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--gt-dir", type=Path, default=DEFAULT_GT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args(argv)

    rows = load_included_rows(args.manifest)
    if args.project_id:
        rows = [r for r in rows if r["project_id"] == args.project_id]
        if not rows:
            print(f"error: {args.project_id} not found among included projects", file=sys.stderr)
            return 1

    results = []
    for row in rows:
        print(f"[audit] {row['project_id']}")
        r = audit_project(row, args.raw_dir, args.processed_dir, args.gt_dir)
        print(f"  -> {r['overall']}")
        results.append(r)

    report = format_report(results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"\nReport written to {args.report}")

    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for r in results:
        counts[r["overall"]] += 1
    print(f"Summary: {counts['PASS']} PASS / {counts['WARN']} WARN / {counts['FAIL']} FAIL (of {len(results)})")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
