"""Data-integrity tests for the ground-truth corpus itself.

`prompts/ground_truth_schema.json` exists but was never referenced anywhere in
src/ or tests/ before this file - confirmed by grep. That means the 21 human
risk registers this whole benchmark is scored against had never been
automatically checked against their own schema; a manual edit to one could
silently break conformance (missing field, wrong type) with nothing catching
it before match.py/metrics.py hit it, or before it became a paper number.

Manually verified once, 2026-07-21: all 21 currently validate. This file turns
that one-time check into a permanent regression guard.

Run: python -m unittest discover -s tests
"""

import csv
import json
import sys
import unittest
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parent.parent
GT_DIR = REPO / "data" / "ground_truth"
MANIFEST_PATH = REPO / "data" / "corpus_manifest.csv"
SCHEMA_PATH = REPO / "prompts" / "ground_truth_schema.json"

sys.path.insert(0, str(REPO / "src"))


def _included_project_ids() -> set[str]:
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        return {r["project_id"] for r in csv.DictReader(f) if r["inclusion_status"] == "included"}


class TestGroundTruthSchemaConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.gt_files = sorted(GT_DIR.glob("*.json"))

    def test_schema_file_itself_is_valid_json_schema(self):
        jsonschema.Draft7Validator.check_schema(self.schema)

    def test_every_ground_truth_file_validates_against_the_schema(self):
        failures = []
        for f in self.gt_files:
            gt = json.loads(f.read_text(encoding="utf-8"))
            try:
                jsonschema.validate(instance=gt, schema=self.schema)
            except jsonschema.ValidationError as e:
                failures.append(f"{f.name}: {e.message} (at {list(e.path)})")
        self.assertEqual(failures, [], "ground-truth file(s) violate their own schema:\n" + "\n".join(failures))

    def test_every_risk_has_a_nonempty_description(self):
        # Schema conformance alone wouldn't catch a technically-valid but
        # empty-string description - a real way a register could quietly
        # become useless ground truth.
        empties = []
        for f in self.gt_files:
            gt = json.loads(f.read_text(encoding="utf-8"))
            for risk in gt.get("risks", []):
                if not (risk.get("description") or "").strip():
                    empties.append(f"{f.name}:{risk.get('risk_id')}")
        self.assertEqual(empties, [], f"risks with empty descriptions: {empties}")

    def test_risk_ids_are_unique_within_each_register(self):
        dupes = []
        for f in self.gt_files:
            gt = json.loads(f.read_text(encoding="utf-8"))
            ids = [r.get("risk_id") for r in gt.get("risks", [])]
            if len(ids) != len(set(ids)):
                dupes.append(f.name)
        self.assertEqual(dupes, [], f"registers with duplicate risk_ids: {dupes}")

    def test_project_id_in_file_matches_the_filename(self):
        mismatches = []
        for f in self.gt_files:
            gt = json.loads(f.read_text(encoding="utf-8"))
            if gt.get("project_id") != f.stem:
                mismatches.append(f"{f.name}: project_id field says {gt.get('project_id')!r}")
        self.assertEqual(mismatches, [], f"filename/project_id mismatches: {mismatches}")


class TestGroundTruthCorpusCoverage(unittest.TestCase):
    """Cross-checks against corpus_manifest.csv - the same class of check that
    caught real gaps earlier this session (AIM4Learning, Sizewell C)."""

    def test_every_included_project_has_a_ground_truth_file(self):
        included = _included_project_ids()
        have_gt = {f.stem for f in GT_DIR.glob("*.json")}
        missing = sorted(included - have_gt)
        self.assertEqual(missing, [], f"included projects with no ground-truth file: {missing}")

    def test_no_ground_truth_file_for_a_non_included_project(self):
        # The inverse gap: a stray ground-truth file for an excluded/set-aside
        # project sitting in the same directory as the real corpus would be
        # confusing at best - e.g. if build_rater_packets.py or match.py ever
        # globbed this directory instead of reading the manifest.
        included = _included_project_ids()
        have_gt = {f.stem for f in GT_DIR.glob("*.json")}
        unexpected = sorted(have_gt - included)
        self.assertEqual(unexpected, [], f"ground-truth files for non-included projects: {unexpected}")


class TestInclusionCriteriaPageCounts(unittest.TestCase):
    """INCLUSION_CRITERIA.md criterion 4: '>=15 pages of planning content
    survive excision' for every included project (the corpus's one HTML-only
    document, with no page count, is explicitly exempted by that doc).

    Also guards remaining_planning_pages' own internal consistency - found
    stale 2026-07-21 for P-UK-PadeswoodCCUS (recorded as 15, but
    total_pages(17) minus the actual excised range (sort_pages union
    section_v_pages, 4 pages) is 13; the field was apparently computed before
    Economic Case Sec 3.4 was added to the excision range alongside Financial
    Case Sec 5.4, and never recalculated). Corrected in the manifest to 13.
    That correction means P-UK-PadeswoodCCUS's 13 pages now sits BELOW the
    documented >=15 threshold despite being included. DECIDED 2026-07-22
    (Madhu): keep as a documented exception rather than exclude - see
    INCLUSION_CRITERIA.md gate 4's disclosed-exception note. This test
    asserts the ARITHMETIC is now internally consistent (no more silent
    staleness), not that every project clears 15 - see the second test
    below, which documents the one known, disclosed exception by name
    rather than silently allowing any future one."""

    HTML_ONLY_NO_PAGE_COUNT = {"P-UK-FreeBreakfastClubs"}
    # The one decided, disclosed exception below the >=15 threshold - see
    # INCLUSION_CRITERIA.md gate 4 and the manifest's own DECIDED 2026-07-22
    # note on this row. Anything else below 15 must fail loudly, not
    # silently join this list.
    KNOWN_BELOW_THRESHOLD = {"P-UK-PadeswoodCCUS": 13}

    def _rows(self):
        with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
            return [r for r in csv.DictReader(f) if r["inclusion_status"] == "included"]

    def test_remaining_planning_pages_matches_total_minus_excised(self):
        sys.path.insert(0, str(REPO / "src"))
        import extract as ex

        mismatches = []
        for r in self._rows():
            pid = r["project_id"]
            total_raw = (r.get("total_pages") or "").strip()
            remaining_raw = (r.get("remaining_planning_pages") or "").strip()
            if not total_raw or not remaining_raw:
                continue
            total_n = int(float(total_raw.split()[0].replace(",", "")))
            remaining_n = int(float(remaining_raw.split()[0].replace(",", "")))
            excised = ex._parse_page_ranges(r.get("sort_pages")) | ex._parse_page_ranges(r.get("section_v_pages"))
            expected = total_n - len(excised)
            if abs(expected - remaining_n) > 1:   # tolerance for off-by-one page-numbering conventions
                mismatches.append(f"{pid}: recorded remaining_planning_pages={remaining_n}, "
                                  f"computed total({total_n})-excised({len(excised)})={expected}")
        self.assertEqual(mismatches, [], "\n".join(mismatches))

    def test_every_included_project_clears_15_pages_or_is_a_disclosed_exception(self):
        failures = []
        for r in self._rows():
            pid = r["project_id"]
            if pid in self.HTML_ONLY_NO_PAGE_COUNT:
                continue
            raw = (r.get("remaining_planning_pages") or "").strip()
            self.assertTrue(raw, f"{pid}: remaining_planning_pages is blank (only the HTML-only "
                                 f"project should lack this field)")
            n = float(raw.split()[0].replace(",", ""))
            if n < 15:
                if pid in self.KNOWN_BELOW_THRESHOLD and self.KNOWN_BELOW_THRESHOLD[pid] == n:
                    continue
                failures.append(f"{pid}: {n} pages, below the >=15 criterion and NOT a known/disclosed exception")
        self.assertEqual(failures, [], "\n".join(failures))


class TestManifestProvenanceFields(unittest.TestCase):
    """Checked 2026-07-21: no duplicate report_no or project_id among included
    rows (both clean). But 5 of 21 included projects have BOTH doc_urls and
    register_url blank - a genuine, if minor, reproducibility gap (no direct
    pointer back to the source document), even though all 5 do carry a real
    World Bank project ID (Pxxxxxx) in their notes field, so they are not
    unidentifiable, just not directly linkable without going through the WB
    project database by hand. Not fixed by guessing/constructing URLs myself
    (a wrong or dead URL recorded as fact would be worse than none - PROJECT_SPEC.md's
    never-fabricate rule applies to provenance links too). This test locks in
    the current 5 as a known, disclosed set so the gap can't silently grow -
    any NEW included project must have at least one of the two URL fields."""

    KNOWN_NO_URL_PROJECTS = {
        "P-STP-YouthEmployment", "P-PER-ArequipaColca", "P-MEX-SustainableValueChains",
        "P-SRB-CompetitivenessJobs", "P-ALB-CitizenServiceDelivery",
    }

    def _rows(self):
        with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
            return [r for r in csv.DictReader(f) if r["inclusion_status"] == "included"]

    def test_no_duplicate_report_no_among_included(self):
        report_nos = [r["report_no"].strip() for r in self._rows() if r.get("report_no", "").strip()]
        from collections import Counter
        dupes = {k: v for k, v in Counter(report_nos).items() if v > 1}
        self.assertEqual(dupes, {}, f"duplicate report_no among included projects: {dupes}")

    def test_no_duplicate_project_id(self):
        with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
            all_ids = [r["project_id"] for r in csv.DictReader(f)]
        from collections import Counter
        dupes = {k: v for k, v in Counter(all_ids).items() if v > 1}
        self.assertEqual(dupes, {}, f"duplicate project_id rows in the manifest: {dupes}")

    def test_missing_url_projects_match_the_known_disclosed_set(self):
        no_url_now = {
            r["project_id"] for r in self._rows()
            if not (r.get("doc_urls") or "").strip() and not (r.get("register_url") or "").strip()
        }
        new_gaps = no_url_now - self.KNOWN_NO_URL_PROJECTS
        self.assertEqual(
            new_gaps, set(),
            f"included project(s) with no doc_urls AND no register_url, not in the "
            f"known/disclosed set: {new_gaps} - either add a real source URL or add "
            f"to KNOWN_NO_URL_PROJECTS with the same justification as the existing 5."
        )


if __name__ == "__main__":
    unittest.main()
