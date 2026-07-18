"""extract.py - convert source PDFs into clean plain text per project.

Reads planning/appraisal PDF(s) for a project and writes a single cleaned text
file to data/processed/<project_id>.txt. Handles multi-file projects (several
PDFs per project) and applies basic cleanup: repeated header/footer removal,
page-number stripping, de-hyphenation, and whitespace normalization.

IMPORTANT (leakage rule, see CLAUDE.md): only ever run this on planning /
appraisal documents. Do NOT extract the human ground-truth risk register with
this tool - that lives separately under data/ground_truth/ as JSON.

Usage:
  # One project from a single PDF or a directory of PDFs:
  python src/extract.py --project-id WB01 --input data/raw/WB01

  # One project from an explicit file:
  python src/extract.py --project-id WB01 --input data/raw/WB01/appraisal.pdf

  # All projects: treats each subdirectory of --raw-dir as one project_id:
  python src/extract.py --all
"""

from __future__ import annotations

import argparse
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


def _normalize_for_match(line: str) -> str:
    """Normalize a line for header/footer frequency comparison.

    Digits are collapsed so that 'Page 3' and 'Page 4' count as the same
    recurring header/footer.
    """
    text = re.sub(r"\d+", "#", line).strip().lower()
    return re.sub(r"\s+", " ", text)


def _find_repeated_lines(pages_lines: list[list[str]]) -> set[str]:
    """Find normalized header/footer lines that recur across many pages."""
    if len(pages_lines) < 3:
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


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract and clean text from a single PDF."""
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF (fitz) is not installed. Run: pip install -r requirements.txt"
        )
    with fitz.open(pdf_path) as doc:
        pages_lines = [page.get_text("text").splitlines() for page in doc]

    repeated = _find_repeated_lines(pages_lines)
    cleaned_pages = ["\n".join(_clean_page(lines, repeated)) for lines in pages_lines]
    text = "\n\n".join(cleaned_pages)
    text = _dehyphenate(text)
    return _normalize_whitespace(text)


def _collect_pdfs(input_path: Path) -> list[Path]:
    """Return the list of PDF files for a project, sorted for stable ordering."""
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(p for p in input_path.rglob("*.pdf"))
    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def extract_project(project_id: str, input_path: Path, output_dir: Path) -> Path:
    """Extract all PDFs for one project into a single cleaned text file."""
    pdfs = _collect_pdfs(input_path)
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found under: {input_path}")

    sections: list[str] = []
    for pdf in pdfs:
        print(f"  [extract] {pdf}")
        body = extract_pdf_text(pdf)
        header = f"===== SOURCE FILE: {pdf.name} ====="
        sections.append(f"{header}\n\n{body}")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{project_id}.txt"
    out_path.write_text("\n\n".join(sections), encoding="utf-8")
    print(f"  -> wrote {out_path} ({len(pdfs)} file(s))")
    return out_path


def _iter_all_projects(raw_dir: Path, output_dir: Path) -> None:
    subdirs = sorted(p for p in raw_dir.iterdir() if p.is_dir())
    if not subdirs:
        print(f"No project subdirectories found in {raw_dir}", file=sys.stderr)
        return
    for sub in subdirs:
        print(f"[project] {sub.name}")
        try:
            extract_project(sub.name, sub, output_dir)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"  !! skipped {sub.name}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-id", help="Project id, e.g. WB01. Output goes to <output-dir>/<project-id>.txt")
    parser.add_argument("--input", type=Path, help="A PDF file or a directory of PDFs for the project.")
    parser.add_argument("--all", action="store_true", help="Process every subdirectory of --raw-dir as one project.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="Root of raw PDFs (default: data/raw).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Where to write text (default: data/processed).")
    args = parser.parse_args(argv)

    if args.all:
        _iter_all_projects(args.raw_dir, args.output_dir)
        return 0

    if not args.project_id or not args.input:
        parser.error("provide --project-id and --input, or use --all")

    try:
        extract_project(args.project_id, args.input, args.output_dir)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
