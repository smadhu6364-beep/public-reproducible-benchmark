"""Unit tests for src/extract.py's pure text/page-range helpers.

Page-range parsing (_parse_page_ranges) is the single highest-historical-bug
surface in this project - the Serbia under-count and the Uganda over-excision
both came down to which pages a manifest field resolves to. These tests pin its
behaviour against the exact messy formats that appear in the real
corpus_manifest.csv. Run: python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import extract  # noqa: E402


class TestParsePageRanges(unittest.TestCase):
    def test_single_page(self):
        self.assertEqual(extract._parse_page_ranges("4"), {4})

    def test_simple_range(self):
        self.assertEqual(extract._parse_page_ranges("17-18"), {17, 18})

    def test_multi_range_comma(self):
        self.assertEqual(extract._parse_page_ranges("10-11, 37-39"), {10, 11, 37, 38, 39})

    def test_real_serbia_format_with_prose(self):
        # "9-10; 30 (restated in Sec V)" -> 9,10,30 (parenthetical prose ignored)
        self.assertEqual(extract._parse_page_ranges("9-10; 30 (restated in Sec V)"), {9, 10, 30})

    def test_real_guatemala_format(self):
        field = "25 (program-level paragraph, not the register used); 37-38 (Guatemala-specific annex, the register this study uses)"
        self.assertEqual(extract._parse_page_ranges(field), {25, 37, 38})

    def test_reversed_range_is_normalized(self):
        # A backwards "38-37" must still yield {37, 38}, not an empty range.
        self.assertEqual(extract._parse_page_ranges("38-37"), {37, 38})

    def test_empty_and_none(self):
        self.assertEqual(extract._parse_page_ranges(""), set())
        self.assertEqual(extract._parse_page_ranges(None), set())

    def test_prose_without_numbers(self):
        self.assertEqual(extract._parse_page_ranges("no pages here"), set())


class TestTextCleanup(unittest.TestCase):
    def test_dehyphenate_joins_broken_words(self):
        self.assertEqual(extract._dehyphenate("infra-\nstructure"), "infrastructure")

    def test_dehyphenate_leaves_normal_hyphens(self):
        # A hyphen not at a line break must be preserved.
        self.assertEqual(extract._dehyphenate("cost-benefit"), "cost-benefit")

    def test_normalize_whitespace_collapses_blank_runs(self):
        out = extract._normalize_whitespace("a\n\n\n\nb")
        self.assertEqual(out, "a\n\nb\n")

    def test_normalize_whitespace_strips_trailing_spaces(self):
        self.assertEqual(extract._normalize_whitespace("a   \nb"), "a\nb\n")

    def test_normalize_for_match_collapses_digits_and_case(self):
        # 'Page 3' and 'Page 4' must normalize identically (recurring header detection).
        self.assertEqual(
            extract._normalize_for_match("Page 3"),
            extract._normalize_for_match("Page 4"),
        )


if __name__ == "__main__":
    unittest.main()
