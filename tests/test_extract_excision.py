"""Unit tests for src/extract.py's page-excision - where this project's real bugs lived.

`_parse_page_ranges` is already covered in test_extract.py. This file covers what
happens with the parsed result: which pages end up in the prompt-safe
`data/processed/` file versus the audit-only `data/risk_source_audit/` file.

Both historical bugs were in this seam. The Serbia under-count left register
pages in the planning text (a leak); the Uganda over-excision cut planning pages
that should have been kept (silently weakening every model's input for that
project). One is a correctness failure, the other a validity failure, and
neither raises an exception - the pipeline just produces a quietly wrong corpus.
So the central assertion here is the partition invariant: every page lands in
exactly one output, and the split is on the manifest's 1-indexed page numbers.

The PDF reader is stubbed - no PyMuPDF, no fixtures on disk.

Run: python -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import extract  # noqa: E402

MANIFEST_HEADER = "project_id,inclusion_status,sort_pages,section_v_pages,other_risk_mentions\n"


def _manifest(tmp: Path, body: str) -> Path:
    p = tmp / "corpus_manifest.csv"
    p.write_text(MANIFEST_HEADER + body, encoding="utf-8")
    return p


class TestLoadExcisionPages(unittest.TestCase):
    def test_unions_sort_and_section_v(self):
        with tempfile.TemporaryDirectory() as td:
            m = _manifest(Path(td), "P-A,included,8-9,17-18,\n")
            self.assertEqual(extract._load_excision_pages("P-A", m), {8, 9, 17, 18})

    def test_either_field_alone_is_enough(self):
        with tempfile.TemporaryDirectory() as td:
            m = _manifest(Path(td), "P-A,included,8-9,,\nP-B,included,,17-18,\n")
            self.assertEqual(extract._load_excision_pages("P-A", m), {8, 9})
            self.assertEqual(extract._load_excision_pages("P-B", m), {17, 18})

    def test_both_blank_returns_none(self):
        # None means "not page-confirmed" -> extract_project must refuse.
        with tempfile.TemporaryDirectory() as td:
            m = _manifest(Path(td), "P-A,included,,,\n")
            self.assertIsNone(extract._load_excision_pages("P-A", m))

    def test_unknown_project_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            m = _manifest(Path(td), "P-A,included,8-9,17-18,\n")
            self.assertIsNone(extract._load_excision_pages("P-NOPE", m))

    def test_missing_manifest_returns_none(self):
        self.assertIsNone(extract._load_excision_pages("P-A", Path("does/not/exist.csv")))

    def test_other_risk_mentions_are_deliberately_not_excised(self):
        # Documented decision (Mexico/Peru/Serbia manifest notes): incidental
        # restatements stay in the planning text. Excising them would over-cut
        # planning content beyond what was validated. Pinned so the "helpful"
        # change of also excising them is a conscious one.
        with tempfile.TemporaryDirectory() as td:
            m = _manifest(Path(td), "P-A,included,8,17,30-31\n")
            self.assertEqual(extract._load_excision_pages("P-A", m), {8, 17})


class _StubbedExtract:
    """Runs extract_project against synthetic pages instead of a real PDF."""

    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        self._patches = [
            mock.patch.object(extract, "_extract_cleaned_pages", return_value=self.pages),
            mock.patch.object(extract, "_collect_pdfs", return_value=[Path("fake/doc.pdf")]),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False


class TestExcisionPartition(unittest.TestCase):
    """Ten pages, each uniquely identifiable, so misrouting is unambiguous."""

    PAGES = [f"PAGE_{i}_CONTENT unique marker for page {i}." for i in range(1, 11)]

    def _run(self, sort_pages="", section_v_pages=""):
        td = tempfile.TemporaryDirectory()
        tmp = Path(td.name)
        m = _manifest(tmp, f"P-A,included,{sort_pages},{section_v_pages},\n")
        out_dir, audit_dir = tmp / "processed", tmp / "audit"
        with _StubbedExtract(self.PAGES):
            with mock.patch("builtins.print"):     # silence the progress chatter
                extract.extract_project("P-A", Path("fake"), out_dir,
                                        risk_audit_dir=audit_dir, manifest_path=m)
        planning = (out_dir / "P-A.txt").read_text(encoding="utf-8")
        audit = (audit_dir / "P-A.txt").read_text(encoding="utf-8")
        td.cleanup()
        return planning, audit

    def test_declared_pages_are_excised_and_the_rest_kept(self):
        planning, audit = self._run(sort_pages="3", section_v_pages="7-8")
        for p in (3, 7, 8):
            self.assertIn(f"PAGE_{p}_CONTENT", audit, f"page {p} should be excised")
            self.assertNotIn(f"PAGE_{p}_CONTENT", planning, f"page {p} LEAKED into planning text")
        for p in (1, 2, 4, 5, 6, 9, 10):
            self.assertIn(f"PAGE_{p}_CONTENT", planning, f"page {p} was wrongly cut")
            self.assertNotIn(f"PAGE_{p}_CONTENT", audit)

    def test_every_page_lands_in_exactly_one_output(self):
        # The invariant that both historical bugs violated: nothing lost,
        # nothing duplicated, regardless of which pages are declared.
        for sort_p, sec_p in [("1", ""), ("10", ""), ("1", "10"), ("3", "7-8"), ("", "5")]:
            with self.subTest(sort=sort_p, section_v=sec_p):
                planning, audit = self._run(sort_pages=sort_p, section_v_pages=sec_p)
                for i in range(1, 11):
                    marker = f"PAGE_{i}_CONTENT"
                    hits = (marker in planning) + (marker in audit)
                    self.assertEqual(hits, 1, f"page {i} appeared in {hits} outputs, expected 1")

    def test_page_numbers_are_one_indexed_not_zero_indexed(self):
        # The off-by-one that would silently shift every excision by a page.
        planning, audit = self._run(sort_pages="1")
        self.assertIn("PAGE_1_CONTENT", audit)
        self.assertNotIn("PAGE_2_CONTENT", audit)
        self.assertIn("PAGE_2_CONTENT", planning)

    def test_last_page_boundary(self):
        planning, audit = self._run(sort_pages="10")
        self.assertIn("PAGE_10_CONTENT", audit)
        self.assertIn("PAGE_9_CONTENT", planning)

    def test_out_of_range_declared_page_is_harmless(self):
        # A manifest typo pointing past the end must not cut a real page.
        planning, audit = self._run(sort_pages="99")
        self.assertEqual(audit, "")
        for i in range(1, 11):
            self.assertIn(f"PAGE_{i}_CONTENT", planning)

    def test_source_header_present_in_both_outputs(self):
        planning, audit = self._run(sort_pages="3")
        self.assertIn("SOURCE FILE: doc.pdf", planning)
        self.assertIn("SOURCE FILE: doc.pdf", audit)


class TestLeakageGuards(unittest.TestCase):
    def test_refuses_to_extract_without_confirmed_pages(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            m = _manifest(tmp, "P-A,included,,,\n")
            with _StubbedExtract(["page one", "page two"]):
                with self.assertRaises(extract.LeakageGuardError) as cm:
                    extract.extract_project("P-A", Path("fake"), tmp / "out", manifest_path=m)
        self.assertIn("no confirmed sort_pages", str(cm.exception))

    def test_leakage_guard_error_is_a_runtime_error(self):
        # Callers catch RuntimeError; the subclass must stay compatible.
        self.assertTrue(issubclass(extract.LeakageGuardError, RuntimeError))

    def test_refuses_when_multiple_pdfs_found(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            m = _manifest(tmp, "P-A,included,3,,\n")
            with mock.patch.object(extract, "_collect_pdfs",
                                   return_value=[Path("a.pdf"), Path("b.pdf")]):
                with self.assertRaises(extract.LeakageGuardError) as cm:
                    extract.extract_project("P-A", Path("fake"), tmp / "out", manifest_path=m)
        self.assertIn("single source", str(cm.exception))

    def test_no_pdf_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            m = _manifest(tmp, "P-A,included,3,,\n")
            with mock.patch.object(extract, "_collect_pdfs", return_value=[]):
                with self.assertRaises(FileNotFoundError):
                    extract.extract_project("P-A", Path("fake"), tmp / "out", manifest_path=m)


class TestHeaderFooterStripping(unittest.TestCase):
    def test_recurring_header_detected_across_pages(self):
        pages = [["The World Bank", "body text here", "1"],
                 ["The World Bank", "different body", "2"],
                 ["The World Bank", "more body", "3"],
                 ["The World Bank", "final body", "4"]]
        repeated = extract._find_repeated_lines(pages)
        self.assertIn("the world bank", repeated)

    def test_page_numbers_collapse_to_one_normalized_form(self):
        # 'Page 3'/'Page 4' must count as the same recurring footer.
        pages = [["hdr", "body", "Page 3"], ["hdr", "body", "Page 4"],
                 ["hdr", "body", "Page 5"], ["hdr", "body", "Page 6"]]
        self.assertIn("page #", extract._find_repeated_lines(pages))

    def test_single_page_document_has_no_repeats(self):
        self.assertEqual(extract._find_repeated_lines([["only", "page"]]), set())

    def test_body_text_outside_the_zone_is_never_treated_as_a_header(self):
        # Only the top/bottom HEADER_FOOTER_ZONE_LINES of each page are
        # considered, so mid-page text can never be stripped as a header no
        # matter how often it recurs.
        pages = [["hdr", "x", "y"] + [f"unique body {i}"] * 4 + ["z", "w", "ftr"]
                 for i in range(6)]
        repeated = extract._find_repeated_lines(pages)
        self.assertIn("hdr", repeated)
        self.assertIn("ftr", repeated)
        self.assertNotIn("unique body #", repeated)

    def test_short_pages_are_entirely_zone(self):
        # Honest limit: on a page with <= 2*HEADER_FOOTER_ZONE_LINES lines the
        # whole page is header/footer zone, so recurring body text there WOULD
        # be stripped. Real PDF pages are far longer, but pinning this means the
        # behaviour is a known property rather than a surprise.
        pages = [["hdr", f"body {i}", "ftr"] for i in range(6)]
        self.assertIn("body #", extract._find_repeated_lines(pages))

    def test_clean_page_drops_repeats_only_in_the_zone(self):
        # A repeated string appearing mid-body is real content, not a header.
        lines = ["The World Bank", "a", "b", "The World Bank", "c", "d", "The World Bank"]
        cleaned = extract._clean_page(lines, {"the world bank"})
        self.assertEqual(cleaned.count("The World Bank"), 1)   # the mid-body one survives

    def test_clean_page_drops_bare_page_numbers(self):
        self.assertNotIn("12", extract._clean_page(["body", "12"], set()))


class TestRealManifestIsExtractable(unittest.TestCase):
    # P-UK-FreeBreakfastClubs is an HTML publication with no PDF and no
    # pagination - its section_v_pages field holds prose, not page numbers, and
    # it has no data/raw/ directory. audit_corpus.py special-cases it the same
    # way (HTML_ONLY_PROJECTS). It is legitimately outside extract.py's
    # PDF-and-page-ranges path, not a project that lost its ranges.
    HTML_ONLY = {"P-UK-FreeBreakfastClubs"}

    def _included(self, manifest):
        import csv
        with open(manifest, newline="", encoding="utf-8") as f:
            return [r["project_id"] for r in csv.DictReader(f)
                    if r["inclusion_status"] == "included"]

    def test_every_pdf_backed_included_project_has_confirmed_excision_pages(self):
        # If any included project lost its page ranges, `extract.py --all` would
        # refuse it with LeakageGuardError - better to know here.
        manifest = Path(__file__).resolve().parent.parent / "data" / "corpus_manifest.csv"
        missing = [pid for pid in self._included(manifest)
                   if pid not in self.HTML_ONLY
                   and extract._load_excision_pages(pid, manifest) is None]
        self.assertEqual(missing, [], f"included projects with no confirmed pages: {missing}")

    def test_html_only_project_refuses_rather_than_mis_excising(self):
        # Its page fields contain prose ("...(HTML, no pagination)"). The safe
        # outcome is None -> LeakageGuardError, NOT a stray page number scraped
        # out of that prose, which would silently cut an arbitrary page.
        manifest = Path(__file__).resolve().parent.parent / "data" / "corpus_manifest.csv"
        for pid in self.HTML_ONLY:
            self.assertIsNone(extract._load_excision_pages(pid, manifest))

    def test_html_only_set_matches_audit_corpus(self):
        # Two modules special-case the same project; they must not drift apart.
        import audit_corpus
        self.assertEqual(self.HTML_ONLY, audit_corpus.HTML_ONLY_PROJECTS)


if __name__ == "__main__":
    unittest.main()
