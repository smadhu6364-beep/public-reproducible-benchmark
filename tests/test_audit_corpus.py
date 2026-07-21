"""Unit tests for src/audit_corpus.py - the leakage auditor.

This is the tool that certifies the corpus is safe to run: it re-derives, from
the original PDFs, whether the human risk register really was excised from the
text models will see. Its dangerous failure mode is not a crash but a **false
negative** - reporting PASS while register text is still sitting in
data/processed/. So the emphasis here is on "does leak_check actually catch a
leak", across the obfuscations a real PDF-to-text pipeline introduces
(re-wrapped lines, collapsed whitespace, case changes).

The PDF-reading path (extract_raw_pages) and the network re-fetch
(audit_free_breakfast_clubs_html) are deliberately not tested here - they need
PyMuPDF and the open internet respectively. Everything below is pure.

Run: python -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import audit_corpus as ac  # noqa: E402


def _risk(rid="R01", description="", mitigation=""):
    return {"risk_id": rid, "description": description, "mitigation": mitigation}


# A realistic register row: long enough to yield 8-word windows.
LEAKY_DESCRIPTION = (
    "Delays in securing cross-boundary land consents could postpone the "
    "construction start date beyond the agreed financial close milestone."
)


class TestLeakCheckCatchesRealLeaks(unittest.TestCase):
    """The false-negative surface. Each test plants register text in the
    processed text in a form a PDF extractor could plausibly produce."""

    def _gt(self, **kw):
        return {"risks": [_risk(description=LEAKY_DESCRIPTION, **kw)]}

    def test_verbatim_leak_is_caught(self):
        res = ac.leak_check(self._gt(), f"Some planning prose. {LEAKY_DESCRIPTION} More prose.")
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any(f["type"] == "verbatim_phrase" for f in res["findings"]))

    def test_leak_rewrapped_across_lines_is_caught(self):
        # PDF extraction re-wraps text; whitespace normalization must see through it.
        rewrapped = LEAKY_DESCRIPTION.replace(" ", "\n   ")
        res = ac.leak_check(self._gt(), f"Planning text.\n{rewrapped}\nEnd.")
        self.assertEqual(res["status"], "FAIL")

    def test_leak_with_different_case_is_caught(self):
        res = ac.leak_check(self._gt(), LEAKY_DESCRIPTION.upper())
        self.assertEqual(res["status"], "FAIL")

    def test_leak_in_the_mitigation_field_is_caught(self):
        mitigation = ("Stage the consent applications ahead of the construction "
                      "programme and hold a contingency in the schedule.")
        gt = {"risks": [_risk(description="Short.", mitigation=mitigation)]}
        res = ac.leak_check(gt, f"Planning prose. {mitigation} More prose.")
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["findings"][0]["type"], "verbatim_phrase")

    def test_fragment_shorter_than_a_window_is_not_caught(self):
        # Documents a real sensitivity limit rather than hiding it: candidate
        # windows are 8 words on a stride of 4, so a surviving fragment shorter
        # than 8 words slips through. Acceptable (an 8-word verbatim overlap is
        # the signal we want, shorter phrases would false-positive constantly),
        # but it is a limit, not a guarantee - worth knowing when reading a PASS.
        mitigation = ("Stage the consent applications ahead of the construction "
                      "programme and hold a contingency in the schedule.")
        gt = {"risks": [_risk(description="Short.", mitigation=mitigation)]}
        res = ac.leak_check(gt, "... hold a contingency in the schedule ...")
        self.assertEqual(res["status"], "PASS")

    def test_partial_leak_of_one_window_is_caught(self):
        # Only a fragment survives excision - still a leak.
        fragment = " ".join(LEAKY_DESCRIPTION.split()[:9])
        res = ac.leak_check(self._gt(), f"unrelated text {fragment} unrelated text")
        self.assertEqual(res["status"], "FAIL")

    def test_clean_processed_text_passes(self):
        res = ac.leak_check(self._gt(), "This appraisal describes the programme's objectives and costs.")
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["findings"], [])

    def test_paraphrase_is_not_flagged(self):
        # The check is verbatim-phrase based by design; a paraphrase passing is
        # a known and accepted limit, pinned here so it stays a choice.
        res = ac.leak_check(self._gt(), "There is some risk that land access might slow the works.")
        self.assertEqual(res["status"], "PASS")


class TestLeakCandidateExtraction(unittest.TestCase):
    def test_citation_brackets_are_stripped(self):
        # '[Financial Case Sec 5.7]' is our own annotation, not source text -
        # it must not be searched for, or every citation would self-trigger.
        cands = ac.extract_leak_candidates(
            _risk(description="[Financial Case Sec 5.7] " + LEAKY_DESCRIPTION))
        self.assertTrue(cands)
        for c in cands:
            self.assertNotIn("Financial Case Sec", c)

    def test_short_risks_yield_no_candidates(self):
        # Under 8 words per sentence -> no window. A known sensitivity limit:
        # very terse register rows cannot be leak-checked by phrase matching.
        self.assertEqual(ac.extract_leak_candidates(_risk(description="Cost overrun risk.")), [])

    def test_windows_are_eight_words(self):
        cands = ac.extract_leak_candidates(_risk(description=LEAKY_DESCRIPTION))
        self.assertTrue(cands)
        for c in cands:
            self.assertEqual(len(c.split()), 8)

    def test_sentences_are_split_and_each_scanned(self):
        two = ("The first sentence here is definitely long enough to window. "
               "The second sentence here is also definitely long enough to window.")
        cands = ac.extract_leak_candidates(_risk(description=two))
        self.assertTrue(any("first sentence" in c for c in cands))
        self.assertTrue(any("second sentence" in c for c in cands))


class TestDistinctiveCodes(unittest.TestCase):
    def test_code_with_digit_is_detected(self):
        codes = ac.extract_distinctive_codes(_risk(description="Register row T1SR1 refers."), set())
        self.assertIn("T1SR1", codes)

    def test_plain_acronyms_without_digits_are_ignored(self):
        # HMG/FID/COD/DESNZ appear all over these documents legitimately.
        codes = ac.extract_distinctive_codes(
            _risk(description="HMG and DESNZ agreed the FID and COD dates."), set())
        self.assertEqual(codes, [])

    def test_own_risk_ids_are_not_treated_as_leaks(self):
        codes = ac.extract_distinctive_codes(
            _risk(rid="R01", description="See R01 and R02 above."), {"R01", "R02"})
        self.assertEqual(codes, [])

    def test_bare_risk_id_pattern_is_ignored(self):
        codes = ac.extract_distinctive_codes(_risk(description="Refer to R123 elsewhere."), set())
        self.assertEqual(codes, [])

    def test_distinctive_code_leak_is_reported_by_leak_check(self):
        gt = {"risks": [_risk(rid="R01", description="Row T1SR1 covers consent risk.")]}
        res = ac.leak_check(gt, "The table lists T1SR1 among the entries.")
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any(f["type"] == "distinctive_code" for f in res["findings"]))


class TestClassifyPageRange(unittest.TestCase):
    def test_exact_match_passes(self):
        status, d = ac.classify_page_range({17, 18}, {17, 18})
        self.assertEqual(status, "PASS")
        self.assertEqual(d["leaked_pages"], [])
        self.assertEqual(d["unverified_declared_pages"], [])

    def test_multipage_block_verified_by_its_first_page_only(self):
        # A section heading appears on page 13 but not its continuation 14 -
        # expected, not a miss. This rule is why the audit isn't drowning in
        # false "unverified" flags.
        status, _ = ac.classify_page_range({13, 14}, {13})
        self.assertEqual(status, "PASS")

    def test_entirely_unfound_block_is_warn(self):
        status, d = ac.classify_page_range({30, 31}, set())
        self.assertEqual(status, "WARN")
        self.assertEqual(d["unverified_declared_pages"], [30, 31])

    def test_adjacent_extra_page_is_warn_not_fail(self):
        # Found page 19 next to declared 17-18: likely the same section
        # spilling over, worth a look but not a stop-the-line.
        status, d = ac.classify_page_range({17, 18}, {17, 18, 19})
        self.assertEqual(status, "WARN")
        self.assertEqual(d["leaked_pages"], [19])

    def test_far_extra_page_is_fail(self):
        status, d = ac.classify_page_range({17, 18}, {17, 18, 60})
        self.assertEqual(status, "FAIL")
        self.assertEqual(d["far_leaked_pages"], [60])

    def test_found_pages_with_nothing_declared_is_fail(self):
        # An undeclared register section found in the PDF is the worst case:
        # nothing was excised because nothing was recorded.
        status, d = ac.classify_page_range(set(), {42})
        self.assertEqual(status, "FAIL")
        self.assertEqual(d["leaked_pages"], [42])

    def test_boundary_two_pages_away_is_still_warn(self):
        self.assertEqual(ac.classify_page_range({17}, {17, 19})[0], "WARN")   # distance 2
        self.assertEqual(ac.classify_page_range({17}, {17, 20})[0], "FAIL")   # distance 3


class TestContiguousBlocks(unittest.TestCase):
    def test_splits_on_gaps(self):
        self.assertEqual(ac._contiguous_blocks({1, 2, 3, 7, 8, 20}), [[1, 2, 3], [7, 8], [20]])

    def test_empty(self):
        self.assertEqual(ac._contiguous_blocks(set()), [])


class TestTocFilter(unittest.TestCase):
    def test_toc_page_detected_by_dot_leaders(self):
        page = ("1.1 Introduction ........... 4\n"
                "1.2 Strategic Case ......... 9\n"
                "3.7 Risk Appraisal ........ 30\n")
        self.assertTrue(ac.is_toc_page(page))

    def test_two_leaders_is_not_enough(self):
        self.assertFalse(ac.is_toc_page("1.1 Intro ..... 4\n1.2 Case ..... 9\n"))

    def test_ordinary_prose_is_not_toc(self):
        self.assertFalse(ac.is_toc_page("The programme will deliver capacity by 2029."))

    def test_toc_page_is_skipped_by_heading_scan(self):
        # Without the filter, a ToC listing every heading matches them all and
        # reports the register as being on the contents page.
        toc = ("I. KEY RISKS ................ 17\n"
               "II. Something ............... 20\n"
               "III. Another ................ 25\n")
        real = "I. KEY RISKS\nThe following risks were identified."
        out = ac.scan_wb_headings([toc, real])
        self.assertEqual(out["key_risks_pages"], [2])   # page 1 (the ToC) skipped


class TestScanWbHeadings(unittest.TestCase):
    def test_key_risks_heading_found(self):
        out = ac.scan_wb_headings(["intro", "IV. KEY RISKS\nrisk prose here"])
        self.assertEqual(out["key_risks_pages"], [2])

    def test_risks_only_heading_found(self):
        out = ac.scan_wb_headings(["intro", "V. RISKS\n"])
        self.assertEqual(out["key_risks_pages"], [2])

    def test_sort_table_requires_hints_and_proximity_to_the_sort_word(self):
        sort_page = ("SORT\nPolitical and Governance: Moderate\n"
                     "Macroeconomic: Low\nFiduciary: Substantial\n")
        out = ac.scan_wb_headings([sort_page])
        self.assertEqual(out["sort_table_pages"], [1])

    def test_narrative_prose_with_hints_but_no_nearby_sort_is_not_a_table(self):
        # Appraisal prose can name 3+ risk categories without being the table.
        prose = ("The political and governance context is stable; macroeconomic "
                 "conditions are sound and fiduciary arrangements are adequate.")
        out = ac.scan_wb_headings([prose, "unrelated", "unrelated"])
        self.assertEqual(out["sort_table_pages"], [])

    def test_continuation_page_within_one_page_of_sort_counts(self):
        # P-BFA case: page 1 has "SORT" + one category, page 2 has the rest.
        p1 = "SORT\nPolitical and Governance: Moderate\n"
        p2 = "Macroeconomic: Low\nFiduciary: Substantial\nStakeholders: Moderate\n"
        out = ac.scan_wb_headings([p1, p2])
        self.assertIn(2, out["sort_table_pages"])


class TestNormAndManifestLoading(unittest.TestCase):
    def test_norm_collapses_whitespace_and_lowercases(self):
        self.assertEqual(ac.norm("  Foo\n\tBAR   baz "), "foo bar baz")

    def test_load_included_rows_filters_on_inclusion_status(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.csv"
            p.write_text(
                "project_id,inclusion_status\n"
                "P-A,included\nP-B,excluded\nP-C,set_aside\nP-D,included\n",
                encoding="utf-8")
            rows = ac.load_included_rows(p)
        self.assertEqual([r["project_id"] for r in rows], ["P-A", "P-D"])

    def test_find_project_pdf_returns_none_when_no_directory(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(ac.find_project_pdf("P-NOPE", Path(td)))

    def test_find_project_pdf_returns_none_when_directory_has_no_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "P-X").mkdir()
            self.assertIsNone(ac.find_project_pdf("P-X", Path(td)))

    def test_find_project_pdf_finds_the_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "P-X"
            d.mkdir()
            (d / "appraisal.pdf").write_bytes(b"%PDF-1.4")
            self.assertEqual(ac.find_project_pdf("P-X", Path(td)).name, "appraisal.pdf")


class TestRealCorpusStillAuditsClean(unittest.TestCase):
    """Runs the pure leak_check against the REAL committed corpus - the
    regression that matters most. If someone re-extracts a project and the
    register comes back into data/processed/, this fails immediately rather
    than at the next manual audit run."""

    def test_no_ground_truth_text_appears_in_any_processed_file(self):
        import json
        repo = Path(__file__).resolve().parent.parent
        gt_dir, proc_dir = repo / "data" / "ground_truth", repo / "data" / "processed"
        failures = []
        for gt_path in sorted(gt_dir.glob("*.json")):
            proc_path = proc_dir / f"{gt_path.stem}.txt"
            if not proc_path.exists():
                continue
            gt = json.loads(gt_path.read_text(encoding="utf-8"))
            res = ac.leak_check(gt, proc_path.read_text(encoding="utf-8"))
            if res["status"] != "PASS":
                failures.append((gt_path.stem, res["findings"][:2]))
        # Known, documented false positives live in
        # results/corpus_audit_review_notes.md - assert against that baseline
        # so a NEW leak is loud while the known ones stay quiet.
        known = {"P-MAR-SecondIdentityTargetingSocialProtection"}
        unexpected = [f for f in failures if f[0] not in known]
        self.assertEqual(unexpected, [], f"NEW leakage detected: {unexpected}")


if __name__ == "__main__":
    unittest.main()
