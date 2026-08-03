"""Task F8 - static assertions tying live code/schema to PROJECT_SPEC.md's actual
written text, so a future silent drift (someone edits one document and not
the other) gets caught by the test suite instead of by someone re-reading
both documents by hand - which is how most of this project's real bugs were
actually found.

These checks read PROJECT_SPEC.md's own text via regex rather than hardcoding a
second transcription of it - if the categories or the 1-5 scale ever change
in PROJECT_SPEC.md itself, this test's expectation moves with it automatically;
only a genuine mismatch between PROJECT_SPEC.md and the schema/code fails it.

NOT duplicated here: the $30 cost-guard threshold is already pinned against
PROJECT_SPEC.md's number in tests/test_run_pipeline.py
(`self.assertEqual(rx.COST_GUARD_THRESHOLD_USD, 30.0)`) - see that file
rather than re-testing it here.

Run: python -m unittest discover -s tests
"""

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC_MD = REPO / "PROJECT_SPEC.md"
OUTPUT_SCHEMA = REPO / "prompts" / "output_schema.json"


def _spec_text() -> str:
    return SPEC_MD.read_text(encoding="utf-8")


def _spec_categories() -> list[str]:
    """Parses the pipe-delimited category list out of PROJECT_SPEC.md's own
    'Output schema' bullet, e.g. '(technical | financial | ... | external)'."""
    m = re.search(r"category\s*\n?\(([^)]+)\)", _spec_text())
    if not m:
        raise AssertionError(
            "Could not find PROJECT_SPEC.md's category list with the expected "
            "'category (a | b | ...)' shape - PROJECT_SPEC.md's wording changed "
            "in a way this parser doesn't handle; update the regex, don't "
            "just hardcode the list instead."
        )
    return [p.strip() for p in m.group(1).split("|")]


def _spec_scale(field: str) -> tuple[int, int]:
    """Parses e.g. 'likelihood (1-5)' or 'impact (1-5)' out of PROJECT_SPEC.md."""
    m = re.search(rf"{field}\s*\((\d)-(\d)\)", _spec_text())
    if not m:
        raise AssertionError(
            f"Could not find PROJECT_SPEC.md's '{field} (N-N)' scale - wording "
            f"changed in a way this parser doesn't handle."
        )
    return int(m.group(1)), int(m.group(2))


def _schema_categories() -> list[str]:
    schema = json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    return schema["$defs"]["risk"]["properties"]["category"]["enum"]


def _schema_scale(field: str) -> tuple[int, int]:
    schema = json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    prop = schema["$defs"]["risk"]["properties"][field]
    return prop["minimum"], prop["maximum"]


class TestOutputSchemaMatchesSpecCategories(unittest.TestCase):
    def test_spec_lists_exactly_8_categories(self):
        # A guard on the guard: if this drops below/above 8, PROJECT_SPEC.md
        # itself changed and every check below needs a human look, not a
        # silently-adjusted assertion count.
        cats = _spec_categories()
        self.assertEqual(
            len(cats), 8,
            f"PROJECT_SPEC.md's category list is no longer 8 items: {cats}. "
            f"The RQs and methodology in PROJECT_SPEC.md are frozen - if this "
            f"changed on purpose, confirm that was intentional before "
            f"updating this test's expectations."
        )

    def test_schema_has_no_extra_categories(self):
        extra = sorted(set(_schema_categories()) - set(_spec_categories()))
        self.assertEqual(
            extra, [],
            f"prompts/output_schema.json's category enum has entries "
            f"PROJECT_SPEC.md doesn't list: {extra}"
        )

    def test_schema_has_no_missing_categories(self):
        missing = sorted(set(_spec_categories()) - set(_schema_categories()))
        self.assertEqual(
            missing, [],
            f"prompts/output_schema.json's category enum is missing "
            f"PROJECT_SPEC.md categories: {missing}"
        )

    def test_likelihood_is_1_to_5_in_both_documents(self):
        spec_scale = _spec_scale("likelihood")
        schema_scale = _schema_scale("likelihood")
        self.assertEqual(spec_scale, (1, 5), "PROJECT_SPEC.md's likelihood scale changed")
        self.assertEqual(schema_scale, (1, 5), "output_schema.json's likelihood scale changed")
        self.assertEqual(
            spec_scale, schema_scale,
            "PROJECT_SPEC.md and output_schema.json disagree on the likelihood scale"
        )

    def test_impact_is_1_to_5_in_both_documents(self):
        spec_scale = _spec_scale("impact")
        schema_scale = _schema_scale("impact")
        self.assertEqual(spec_scale, (1, 5), "PROJECT_SPEC.md's impact scale changed")
        self.assertEqual(schema_scale, (1, 5), "output_schema.json's impact scale changed")
        self.assertEqual(
            spec_scale, schema_scale,
            "PROJECT_SPEC.md and output_schema.json disagree on the impact scale"
        )


class TestRepoStructureMatchesSpec(unittest.TestCase):
    """Directories/files PROJECT_SPEC.md's 'Repo structure (maintain exactly)'
    section names explicitly."""

    def test_documented_directories_exist(self):
        expected_dirs = [
            "data/raw",
            "data/processed",
            "data/ground_truth",
            "prompts",
            "src",
            "results/raw_outputs",
            "results/scored",
            "analysis/figures",
        ]
        missing = [d for d in expected_dirs if not (REPO / d).is_dir()]
        self.assertEqual(
            missing, [],
            f"PROJECT_SPEC.md's repo-structure section names these directories, "
            f"but they don't exist on disk: {missing}"
        )

    def test_documented_manifest_file_exists(self):
        self.assertTrue(
            (REPO / "data" / "corpus_manifest.csv").is_file(),
            "PROJECT_SPEC.md names data/corpus_manifest.csv explicitly"
        )

    def test_documented_prompt_files_exist(self):
        expected = ["zero_shot.txt", "few_shot.txt", "structured.txt", "output_schema.json"]
        missing = [f for f in expected if not (REPO / "prompts" / f).is_file()]
        self.assertEqual(
            missing, [],
            f"PROJECT_SPEC.md names these files under prompts/: {missing} missing"
        )

    def test_documented_src_files_exist(self):
        expected = ["extract.py", "run_experiments.py", "match.py", "metrics.py", "judge.py"]
        missing = [f for f in expected if not (REPO / "src" / f).is_file()]
        self.assertEqual(
            missing, [],
            f"PROJECT_SPEC.md names these files under src/: {missing} missing"
        )


if __name__ == "__main__":
    unittest.main()
