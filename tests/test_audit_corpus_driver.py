"""Unit tests for src/audit_corpus.py's orchestration: audit_project()'s
overall-status aggregation and main()'s CLI. test_audit_corpus.py already
covers the pure checks (leak_check, classify_page_range, scan_wb_headings);
this file covers the layer that ties per-check statuses into one verdict per
project and drives the report end to end - untested until now, and the exact
kind of aggregation logic (SKIPPED handling, FAIL-beats-WARN-beats-PASS) that's
easy to get subtly wrong without anyone noticing on the real, mostly-PASS
corpus.

audit_page_ranges/leak_check/audit_free_breakfast_clubs_html are stubbed via
mock.patch.object so these tests control exactly which check produces which
status, rather than depending on a real PDF or the internet.

Run: python -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import audit_corpus as ac  # noqa: E402


def _row(project_id="P-TEST", **extra):
    row = {"project_id": project_id, "sort_pages": "", "section_v_pages": ""}
    row.update(extra)
    return row


class TestAuditProjectFileExistence(unittest.TestCase):
    """check2 depends on the ground-truth and processed files actually
    existing - the two ways that can fail before leak_check ever runs."""

    def test_missing_ground_truth_file_is_a_fail(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "processed").mkdir()
            (tmp / "processed" / "P-TEST.txt").write_text("planning text", encoding="utf-8")
            with mock.patch.object(ac, "audit_page_ranges", return_value={"status": "PASS"}):
                result = ac.audit_project(_row(), tmp / "raw", tmp / "processed", tmp / "gt")
        self.assertEqual(result["check2"]["status"], "FAIL")
        self.assertEqual(result["check2"]["findings"][0]["type"], "missing_ground_truth_file")
        self.assertEqual(result["overall"], "FAIL")

    def test_missing_processed_file_is_a_fail(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "gt").mkdir()
            (tmp / "gt" / "P-TEST.json").write_text('{"risks": []}', encoding="utf-8")
            with mock.patch.object(ac, "audit_page_ranges", return_value={"status": "PASS"}):
                result = ac.audit_project(_row(), tmp / "raw", tmp / "processed", tmp / "gt")
        self.assertEqual(result["check2"]["status"], "FAIL")
        self.assertEqual(result["check2"]["findings"][0]["type"], "missing_processed_file")
        self.assertEqual(result["overall"], "FAIL")


class TestAuditProjectStatusAggregation(unittest.TestCase):
    """The FAIL > WARN > PASS aggregation logic, and that SKIPPED never
    counts toward the verdict either way."""

    def _project_with(self, check1_status, check2_status, td):
        tmp = Path(td)
        (tmp / "gt").mkdir()
        (tmp / "processed").mkdir()
        (tmp / "gt" / "P-TEST.json").write_text('{"risks": []}', encoding="utf-8")
        (tmp / "processed" / "P-TEST.txt").write_text("planning text", encoding="utf-8")
        with mock.patch.object(ac, "audit_page_ranges", return_value={"status": check1_status}), \
             mock.patch.object(ac, "leak_check", return_value={"status": check2_status, "findings": []}):
            return ac.audit_project(_row(), tmp / "raw", tmp / "processed", tmp / "gt")

    def test_both_pass_is_overall_pass(self):
        with tempfile.TemporaryDirectory() as td:
            result = self._project_with("PASS", "PASS", td)
        self.assertEqual(result["overall"], "PASS")

    def test_any_warn_with_no_fail_is_overall_warn(self):
        with tempfile.TemporaryDirectory() as td:
            result = self._project_with("WARN", "PASS", td)
        self.assertEqual(result["overall"], "WARN")

    def test_any_fail_wins_over_warn(self):
        with tempfile.TemporaryDirectory() as td:
            result = self._project_with("WARN", "FAIL", td)
        self.assertEqual(result["overall"], "FAIL")

    def test_leak_check_fail_alone_is_overall_fail(self):
        with tempfile.TemporaryDirectory() as td:
            result = self._project_with("PASS", "FAIL", td)
        self.assertEqual(result["overall"], "FAIL")


class TestAuditProjectHtmlOnlySpecialCase(unittest.TestCase):
    def test_html_only_project_skips_check1_and_runs_check2b_instead(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "gt").mkdir()
            (tmp / "processed").mkdir()
            (tmp / "gt" / "P-UK-FreeBreakfastClubs.json").write_text('{"risks": []}', encoding="utf-8")
            (tmp / "processed" / "P-UK-FreeBreakfastClubs.txt").write_text("planning", encoding="utf-8")
            with mock.patch.object(ac, "leak_check", return_value={"status": "PASS", "findings": []}), \
                 mock.patch.object(ac, "audit_free_breakfast_clubs_html", return_value={"status": "PASS", "findings": []}):
                result = ac.audit_project(_row("P-UK-FreeBreakfastClubs"), tmp / "raw", tmp / "processed", tmp / "gt")
        self.assertEqual(result["check1"]["status"], "SKIPPED")
        self.assertIn("check2b_html", result)
        self.assertEqual(result["overall"], "PASS")   # SKIPPED must not drag down the verdict

    def test_html_only_project_check2b_fail_still_fails_overall(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "gt").mkdir()
            (tmp / "processed").mkdir()
            (tmp / "gt" / "P-UK-FreeBreakfastClubs.json").write_text('{"risks": []}', encoding="utf-8")
            (tmp / "processed" / "P-UK-FreeBreakfastClubs.txt").write_text("planning", encoding="utf-8")
            with mock.patch.object(ac, "leak_check", return_value={"status": "PASS", "findings": []}), \
                 mock.patch.object(ac, "audit_free_breakfast_clubs_html",
                                   return_value={"status": "FAIL", "findings": [{"type": "risk_bullets_leaked_into_processed"}]}):
                result = ac.audit_project(_row("P-UK-FreeBreakfastClubs"), tmp / "raw", tmp / "processed", tmp / "gt")
        self.assertEqual(result["overall"], "FAIL")


class TestAuditProjectPageRangeErrorHandling(unittest.TestCase):
    def test_exception_during_page_range_audit_is_caught_as_a_fail_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "gt").mkdir()
            (tmp / "processed").mkdir()
            (tmp / "gt" / "P-TEST.json").write_text('{"risks": []}', encoding="utf-8")
            (tmp / "processed" / "P-TEST.txt").write_text("planning", encoding="utf-8")
            with mock.patch.object(ac, "audit_page_ranges", side_effect=RuntimeError("PDF corrupt")):
                result = ac.audit_project(_row(), tmp / "raw", tmp / "processed", tmp / "gt")
        self.assertEqual(result["check1"]["status"], "FAIL")
        self.assertIn("PDF corrupt", result["check1"]["detail"])
        self.assertEqual(result["overall"], "FAIL")


class TestMainCLI(unittest.TestCase):
    def _corpus(self, td, projects):
        tmp = Path(td)
        for d in ("gt", "processed", "raw"):
            (tmp / d).mkdir(exist_ok=True)
        manifest = tmp / "manifest.csv"
        with open(manifest, "w", encoding="utf-8") as f:
            f.write("project_id,inclusion_status,sort_pages,section_v_pages\n")
            for pid in projects:
                f.write(f"{pid},included,,\n")
                (tmp / "gt" / f"{pid}.json").write_text('{"risks": []}', encoding="utf-8")
                (tmp / "processed" / f"{pid}.txt").write_text("planning", encoding="utf-8")
        return tmp, manifest

    def test_all_pass_returns_exit_zero_and_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            tmp, manifest = self._corpus(td, ["P-A", "P-B"])
            report_path = tmp / "report.md"
            with mock.patch.object(ac, "audit_page_ranges", return_value={"status": "PASS"}), \
                 mock.patch.object(ac, "leak_check", return_value={"status": "PASS", "findings": []}):
                code = ac.main([
                    "--manifest", str(manifest), "--raw-dir", str(tmp / "raw"),
                    "--processed-dir", str(tmp / "processed"), "--gt-dir", str(tmp / "gt"),
                    "--report", str(report_path),
                ])
            self.assertEqual(code, 0)
            report = report_path.read_text(encoding="utf-8")
        self.assertIn("2 PASS / 0 WARN / 0 FAIL", report)

    def test_any_fail_returns_exit_one(self):
        with tempfile.TemporaryDirectory() as td:
            tmp, manifest = self._corpus(td, ["P-A", "P-B"])
            with mock.patch.object(ac, "audit_page_ranges", return_value={"status": "PASS"}), \
                 mock.patch.object(ac, "leak_check", side_effect=[
                     {"status": "PASS", "findings": []}, {"status": "FAIL", "findings": [{"type": "verbatim_phrase", "risk_id": "R01", "text": "x"}]}]):
                code = ac.main([
                    "--manifest", str(manifest), "--raw-dir", str(tmp / "raw"),
                    "--processed-dir", str(tmp / "processed"), "--gt-dir", str(tmp / "gt"),
                    "--report", str(tmp / "report.md"),
                ])
        self.assertEqual(code, 1)

    def test_project_id_filters_to_a_single_project(self):
        with tempfile.TemporaryDirectory() as td:
            tmp, manifest = self._corpus(td, ["P-A", "P-B"])
            with mock.patch.object(ac, "audit_page_ranges", return_value={"status": "PASS"}), \
                 mock.patch.object(ac, "leak_check", return_value={"status": "PASS", "findings": []}):
                code = ac.main([
                    "--manifest", str(manifest), "--project-id", "P-A",
                    "--raw-dir", str(tmp / "raw"), "--processed-dir", str(tmp / "processed"),
                    "--gt-dir", str(tmp / "gt"), "--report", str(tmp / "report.md"),
                ])
            report = (tmp / "report.md").read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("P-A", report)
        self.assertNotIn("## P-B", report)

    def test_unknown_project_id_returns_exit_one_without_crashing(self):
        with tempfile.TemporaryDirectory() as td:
            tmp, manifest = self._corpus(td, ["P-A"])
            code = ac.main([
                "--manifest", str(manifest), "--project-id", "P-DOES-NOT-EXIST",
                "--raw-dir", str(tmp / "raw"), "--processed-dir", str(tmp / "processed"),
                "--gt-dir", str(tmp / "gt"), "--report", str(tmp / "report.md"),
            ])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
