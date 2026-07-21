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


if __name__ == "__main__":
    unittest.main()
