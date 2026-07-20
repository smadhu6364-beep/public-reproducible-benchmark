"""extract.py - convert source PDFs into clean plain text per project.

Reads planning/appraisal PDF(s) for a project and writes a single cleaned text
file to data/processed/<project_id>.txt. Handles multi-file projects (several
PDFs per project) and applies basic cleanup: repeated header/footer removal,
page-number stripping, de-hyphenation, and whitespace normalization.

LEAKAGE RULE (see CLAUDE.md, "critical"): only ever run this on planning /
appraisal documents -- and even then, the SORT risk-rating table and the Key
Risks narrative section embedded IN those same PAD documents must never reach
data/processed/. This module enforces that automatically:

  - Every project's SORT-table and Key-Risks page ranges are read from
    data/corpus_manifest.csv (columns sort_pages, section_v_pages) --
    independently re-verified page numbers, not guessed by this script.
  - Those pages are cut from the PDF before anything is written to
    data/processed/<project_id>.txt (the prompt-safe planning text).
  - The cut pages are written separately to
    data/risk_source_audit/<project_id>.txt -- for human audit only, NEVER
    to be loaded into a prompt or few-shot example. This mirrors the dual
    output (planning/ + risk_source/) that scratch/excise_prototype.py
    already validated by hand against all 5 real source PDFs this session.
  - If a project has no manifest row, or its sort_pages AND section_v_pages
    are both blank (i.e. not yet page-confirmed -- see
    scratch/verify_new_candidates.py), extraction REFUSES with
    LeakageGuardError rather than silently writing un-excised text. There is
    deliberately no flag to bypass this.

Why this exists: earlier in this project, corpus_manifest.csv recorded
Serbia's Key Risks range as "30-31" when the real range (confirmed by direct
PDF re-extraction) is "30-32" -- page 32 alone contains 3 of 6 ground-truth
risks verbatim. That bug was caught by manual re-verification, not by any
script. This guard narrows, but does not eliminate, the need for that same
manual page-range verification before a project's manifest row is trusted
here -- garbage page ranges in still means garbage (leaky) output out.

Usage:
  # One project from a single PDF or a directory of PDFs:
  python src/extract.py --project-id P-ALB-CitizenServiceDelivery --input data/raw/P-ALB-CitizenServiceDelivery

  # One project from an explicit file:
  python src/extract.py --project-id WB01 --input data/raw/WB01/appraisal.pdf

  # All projects: treats each subdirectory of --raw-dir as one project_id:
  python src/extract.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - dependency not installed yet
    fitz = None

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_OUTPUT_DIR = Path("data/processed")
DEFAULT_RISK_AUDIT_DIR = Path("data/risk_source_audit")
DEFAULT_MANIFEST_PATH = Path("data/corpus_manifest.csv")

# A line is treated as a candidate header/footer if it appears (normalized) on
# at least this fraction of pages. Kept conservative to avoid deleting content.
HEADER_FOOTER_MIN_FRACTION = 0.5
# Only the first/last N lines of each page are considered header/footer zones.
HEADER_FOOTER_ZONE_LINES = 3

# Lines that are pure page markers.
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s*)?\d+\s*(?:/|of)\s*\d+\s*$", re.IGNORECASE
)
_BARE_NUMBER_RE = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")

# Matches "17-18", "4", or "30" wherever it appears inside a messier manifest
# field like "9-10; 30 (restated in Sec V)" -- deliberately permissive, since
# these fields are human-written notes, not a strict machine format.
_PAGE_TOKEN_RE = re.compile(r"(\d+)\s*-\s*(\d+)|(\d+)")


class LeakageGuardError(RuntimeError):
    """A project cannot be safely excised. Never bypass this - fix the
    manifest (get confirmed page ranges) instead."""


def _parse_page_ranges(field: str | None) -> set[int]:
    """Extract every page number referenced in a manifest page-range field.

    Handles the real formats seen in corpus_manifest.csv, e.g. "17-18", "4",
    "9-10; 30 (restated in Sec V)" -- pulls out every bare number and every
    N-M range found anywhere in the string, ignoring surrounding prose and
    parenthetical notes.
    """
    pages: set[int] = set()
    if not field:
        return pages
    for m in _PAGE_TOKEN_RE.finditer(field):
        if m.group(1) and m.group(2):
            lo, hi = int(m.group(1)), int(m.group(2))
            pages.update(range(min(lo, hi), max(lo, hi) + 1))
        elif m.group(3):
            pages.add(int(m.group(3)))
    return pages


def _load_excision_pages(project_id: str, manifest_path: Path) -> set[int] | None:
    """Return the 1-indexed PDF pages to excise for a project, or None if the
    project has no manifest row, or has one but isn't yet page-confirmed
    (both sort_pages and section_v_pages blank).

    Deliberately does NOT fall back to other_risk_mentions pages: those are
    recorded as incidental restatements found during this session's leakage
    audits (e.g. an appraisal-summary paragraph that happens to echo risk
    language), already investigated and left in planning text on purpose --
    see corpus_manifest.csv notes for Mexico/Peru/Serbia. Excising them too
    would silently over-cut planning content beyond what was validated.
    """
    if not manifest_path.exists():
        return None
    with open(manifest_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    row = next((r for r in rows if r.get("project_id") == project_id), None)
    if row is None:
        return None
    sort_pages = _parse_page_ranges(row.get("sort_pages"))
    section_v_pages = _parse_page_ranges(row.get("section_v_pages"))
    if not sort_pages and not section_v_pages:
        return None
    return sort_pages | section_v_pages


def _normalize_for_match(line: str) -> str:
    """Normalize a line for header/footer frequency comparison.

    Digits are collapsed so that 'Page 3' and 'Page 4' count as the same
    recurring header/footer.
    """
    text = re.sub(r"\d+", "#", line).strip().lower()
    return re.sub(r"\s+", " ", text)


def _find_repeated_lines(pages_lines: list[list[str]]) -> set[str]:
    """Find normalized header/footer lines that recur across many pages.

    Runs across the FULL document (all pages), before any excision split --
    this keeps header/footer detection statistically accurate even when the
    Key Risks section is only 1-2 pages, which wouldn't have enough pages on
    its own to clear the recurrence threshold.
    """
    # Need at least two pages for anything to "recur"; single-page docs are skipped.
    if len(pages_lines) < 2:
        return set()

    counter: Counter[str] = Counter()
    for lines in pages_lines:
        zone: list[str] = []
        zone.extend(lines[:HEADER_FOOTER_ZONE_LINES])
        zone.extend(lines[-HEADER_FOOTER_ZONE_LINES:])
        seen_on_page = set()
        for line in zone:
            norm = _normalize_for_match(line)
            if norm and norm not in seen_on_page:
                counter[norm] += 1
                seen_on_page.add(norm)

    threshold = max(2, int(len(pages_lines) * HEADER_FOOTER_MIN_FRACTION))
    return {norm for norm, count in counter.items() if count >= threshold}


def _clean_page(lines: list[str], repeated: set[str]) -> list[str]:
    """Drop page numbers and known repeated header/footer lines from a page."""
    cleaned: list[str] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if _PAGE_NUMBER_RE.match(stripped) or _BARE_NUMBER_RE.match(stripped):
            continue
        in_zone = idx < HEADER_FOOTER_ZONE_LINES or idx >= len(lines) - HEADER_FOOTER_ZONE_LINES
        if in_zone and _normalize_for_match(stripped) in repeated:
            continue
        cleaned.append(line.rstrip())
    return cleaned


def _dehyphenate(text: str) -> str:
    """Join words broken across line ends: 'infra-\\nstructure' -> 'infrastructure'."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of blank lines and trailing spaces."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _extract_cleaned_pages(pdf_path: Path) -> list[str]:
    """Extract per-page cleaned text. List index i corresponds to PDF page i+1
    (1-indexed page number), so callers can filter by page number directly.
    """
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF (fitz) is not installed. Run: pip install -r requirements.txt"
        )
    with fitz.open(pdf_path) as doc:
        pages_lines = [page.get_text("text").splitlines() for page in doc]

    repeated = _find_repeated_lines(pages_lines)
    return ["\n".join(_clean_page(lines, repeated)) for lines in pages_lines]


def _assemble(pages: list[str]) -> str:
    """Join a subset of cleaned pages into final normalized text."""
    text = "\n\n".join(pages)
    text = _dehyphenate(text)
    return _normalize_whitespace(text)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract and clean the FULL text of a single PDF, with no excision.

    Kept for callers that genuinely want raw full-document text (e.g. ad hoc
    inspection). Never used by extract_project() below -- that path always
    goes through the excision guard.
    """
    return _assemble(_extract_cleaned_pages(pdf_path))


def _collect_pdfs(input_path: Path) -> list[Path]:
    """Return the list of PDF files for a project, sorted for stable ordering."""
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(p for p in input_path.rglob("*.pdf"))
    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def extract_project(
    project_id: str,
    input_path: Path,
    output_dir: Path,
    risk_audit_dir: Path = DEFAULT_RISK_AUDIT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> Path:
    """Extract one project's PDF into leakage-free planning text.

    Writes:
      output_dir/<project_id>.txt       -- planning text only, prompt-safe.
      risk_audit_dir/<project_id>.txt   -- excised SORT + Key Risks pages,
                                            audit only, never for prompting.

    Raises LeakageGuardError (a RuntimeError subclass, so existing callers'
    `except RuntimeError` handling still catches it) if:
      - the project has no confirmed sort_pages/section_v_pages in the
        manifest, or
      - more than one PDF is found for the project (the manifest's page
        ranges assume a single source document; guessing which file they
        apply to is unsafe).
    """
    pdfs = _collect_pdfs(input_path)
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found under: {input_path}")

    excise_pages = _load_excision_pages(project_id, manifest_path)
    if excise_pages is None:
        raise LeakageGuardError(
            f"{project_id}: no confirmed sort_pages/section_v_pages in "
            f"{manifest_path}. Refusing to extract -- cannot guarantee the "
            f"SORT table and Key Risks narrative won't leak into "
            f"{output_dir / (project_id + '.txt')}. Run "
            f"scratch/verify_new_candidates.py to get confirmed page ranges, "
            f"record them in the manifest, then retry."
        )

    if len(pdfs) != 1:
        raise LeakageGuardError(
            f"{project_id}: {len(pdfs)} PDF files found under {input_path}, "
            f"but corpus_manifest.csv's page ranges assume a single source "
            f"PDF. Refusing to guess which file the recorded pages apply to."
        )

    pdf = pdfs[0]
    print(f"  [extract] {pdf}")
    cleaned_pages = _extract_cleaned_pages(pdf)  # index i -> page i+1

    planning_pages = [
        text for i, text in enumerate(cleaned_pages) if (i + 1) not in excise_pages
    ]
    risk_pages = [
        text for i, text in enumerate(cleaned_pages) if (i + 1) in excise_pages
    ]

    header = f"===== SOURCE FILE: {pdf.name} ====="
    planning_text = f"{header}\n\n{_assemble(planning_pages)}"
    risk_text = f"{header}\n\n{_assemble(risk_pages)}" if risk_pages else ""

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{project_id}.txt"
    out_path.write_text(planning_text, encoding="utf-8")

    risk_audit_dir.mkdir(parents=True, exist_ok=True)
    risk_out_path = risk_audit_dir / f"{project_id}.txt"
    risk_out_path.write_text(risk_text, encoding="utf-8")

    print(f"  -> wrote {out_path} (planning, {len(planning_pages)}/{len(cleaned_pages)} pages)")
    print(
        f"  -> wrote {risk_out_path} (excised SORT+Key Risks, "
        f"{len(risk_pages)} pages -- AUDIT ONLY, never prompt with this file)"
    )
    return out_path


def _iter_all_projects(
    raw_dir: Path,
    output_dir: Path,
    risk_audit_dir: Path = DEFAULT_RISK_AUDIT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> None:
    subdirs = sorted(p for p in raw_dir.iterdir() if p.is_dir())
    if not subdirs:
        print(f"No project subdirectories found in {raw_dir}", file=sys.stderr)
        return
    for sub in subdirs:
        print(f"[project] {sub.name}")
        try:
            extract_project(sub.name, sub, output_dir, risk_audit_dir, manifest_path)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"  !! skipped {sub.name}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-id", help="Project id, e.g. WB01. Output goes to <output-dir>/<project-id>.txt")
    parser.add_argument("--input", type=Path, help="A PDF file or a directory of PDFs for the project.")
    parser.add_argument("--all", action="store_true", help="Process every subdirectory of --raw-dir as one project.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="Root of raw PDFs (default: data/raw).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Where to write planning text (default: data/processed).")
    parser.add_argument(
        "--risk-audit-dir", type=Path, default=DEFAULT_RISK_AUDIT_DIR,
        help="Where excised SORT+Key Risks pages are written for audit only -- "
             "NEVER prompt with this (default: data/risk_source_audit).",
    )
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST_PATH,
        help="corpus_manifest.csv path, used to look up confirmed excision "
             "page ranges (default: data/corpus_manifest.csv).",
    )
    args = parser.parse_args(argv)

    if args.all:
        _iter_all_projects(args.raw_dir, args.output_dir, args.risk_audit_dir, args.manifest)
        return 0

    if not args.project_id or not args.input:
        parser.error("provide --project-id and --input, or use --all")

    try:
        extract_project(args.project_id, args.input, args.output_dir, args.risk_audit_dir, args.manifest)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
