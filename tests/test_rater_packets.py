"""Unit tests for src/build_rater_packets.py - Method B sampling and blinding.

This module is the one place where a silent bug invalidates human data rather
than just producing a wrong number: if a packet reveals which model or prompt
produced a register, or if the per-rater orders correlate, the expert-Likert
arm (CLAUDE.md Method B) is compromised - and you would find out only after
raters had already read the packets. So the blinding assertions here are
deliberately paranoid, and they check the SHAREABLE artifacts specifically
(packets + rater_assignments), not just the internal data structures.

Note on what blinding does and does not hide: raters legitimately see the
project's planning documentation (they need it to judge the register), so a
packet does identify the project. What must never leak is the MODEL and PROMPT
STRATEGY behind the register, and the ground-truth human register.

Run: python -m unittest discover -s tests
"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import build_rater_packets as brp  # noqa: E402

POOL = [f"P-X{i:02d}-Project" for i in range(1, 19)] + [
    "P-UK-Alpha", "P-UK-Beta", "P-UK-Gamma",
]
N_CELLS = len(brp.MODELS) * len(brp.PROMPTS)  # 3 x 3


class TestSampleCells(unittest.TestCase):
    def test_cell_count_and_size(self):
        regs = brp.sample_cells(POOL, per_cell=5, min_uk_per_cell=0, seed=1)
        self.assertEqual(len(regs), N_CELLS * 5)
        cells = {r["cell"] for r in regs}
        self.assertEqual(len(cells), N_CELLS)
        for cell in cells:
            self.assertEqual(len([r for r in regs if r["cell"] == cell]), 5)

    def test_projects_distinct_within_a_cell(self):
        # Sampling is without replacement *within* a cell; a project may recur
        # across cells (rater_protocol section 3.1).
        regs = brp.sample_cells(POOL, per_cell=5, min_uk_per_cell=1, seed=7)
        for cell in {r["cell"] for r in regs}:
            pids = [r["project_id"] for r in regs if r["cell"] == cell]
            self.assertEqual(len(pids), len(set(pids)), f"duplicate project in cell {cell}")

    def test_same_seed_reproduces_exactly(self):
        a = brp.sample_cells(POOL, 5, 1, seed=20260720)
        b = brp.sample_cells(POOL, 5, 1, seed=20260720)
        self.assertEqual(a, b)

    def test_different_seed_changes_sample(self):
        a = brp.sample_cells(POOL, 5, 1, seed=1)
        b = brp.sample_cells(POOL, 5, 1, seed=2)
        self.assertNotEqual(a, b)

    def test_min_uk_per_cell_guarantees_uk_in_every_cell(self):
        # The decided setting (Madhu, 2026-07-20): --min-uk-per-cell 1.
        for seed in range(30):
            regs = brp.sample_cells(POOL, 5, min_uk_per_cell=1, seed=seed)
            for cell in {r["cell"] for r in regs}:
                uk = [r for r in regs if r["cell"] == cell and brp.is_uk(r["project_id"])]
                self.assertGreaterEqual(len(uk), 1, f"seed {seed} cell {cell} has no UK register")

    def test_min_uk_zero_can_leave_a_cell_with_no_uk(self):
        # This is the failure mode that motivated exposing --min-uk-per-cell at
        # all: a naive draw (0) can and does produce UK-less cells. Asserted
        # over a fixed seed range so the test stays deterministic.
        found_uk_less_cell = False
        for seed in range(30):
            regs = brp.sample_cells(POOL, 5, min_uk_per_cell=0, seed=seed)
            for cell in {r["cell"] for r in regs}:
                if not any(brp.is_uk(r["project_id"]) for r in regs if r["cell"] == cell):
                    found_uk_less_cell = True
                    break
            if found_uk_less_cell:
                break
        self.assertTrue(
            found_uk_less_cell,
            "expected the unstratified draw to miss UK in some cell across 30 seeds",
        )

    def test_min_uk_can_be_exceeded_by_the_random_remainder(self):
        # min_uk is a floor, not a quota - the remaining draw is over the whole
        # pool and may pull additional UK projects.
        counts = [
            sum(1 for r in brp.sample_cells(POOL, 5, 1, seed=s) if brp.is_uk(r["project_id"]))
            for s in range(20)
        ]
        self.assertGreaterEqual(min(counts), N_CELLS)      # >= 1 per cell
        self.assertGreater(max(counts), N_CELLS)           # sometimes more

    def test_per_cell_larger_than_pool_raises(self):
        with self.assertRaises(ValueError):
            brp.sample_cells(POOL, per_cell=len(POOL) + 1, min_uk_per_cell=0, seed=1)

    def test_min_uk_exceeding_uk_pool_raises(self):
        with self.assertRaises(ValueError):
            brp.sample_cells(POOL, per_cell=5, min_uk_per_cell=4, seed=1)  # only 3 UK

    def test_min_uk_exceeding_per_cell_raises(self):
        with self.assertRaises(ValueError):
            brp.sample_cells(POOL, per_cell=2, min_uk_per_cell=3, seed=1)


class TestAssignCodes(unittest.TestCase):
    def _regs(self, seed=1):
        return brp.assign_codes(brp.sample_cells(POOL, 5, 1, seed=seed), seed=seed)

    def test_codes_unique_and_well_formed(self):
        regs = self._regs()
        codes = [r["code"] for r in regs]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(codes), N_CELLS * 5)
        for c in codes:
            self.assertRegex(c, r"^REG-\d{3}$")

    def test_code_order_does_not_track_cell_order(self):
        # A code's number must leak nothing about its cell. If codes were
        # assigned in grid order, the cell sequence sorted by code would be the
        # grid sequence (claude/zero_shot x5, claude/few_shot x5, ...).
        regs = self._regs()
        by_code = [r["cell"] for r in sorted(regs, key=lambda r: r["code"])]
        grid_order = [f"{m}/{p}" for m in brp.MODELS for p in brp.PROMPTS for _ in range(5)]
        self.assertNotEqual(by_code, grid_order)

    def test_deterministic(self):
        self.assertEqual(self._regs(seed=5), self._regs(seed=5))


class TestPerRaterOrders(unittest.TestCase):
    def _codes(self):
        return [f"REG-{i:03d}" for i in range(1, 46)]

    def test_every_rater_gets_every_code_once(self):
        orders = brp.per_rater_orders(self._codes(), n_raters=4, seed=1)
        self.assertEqual(len(orders), 4)
        for rater, order in orders.items():
            self.assertEqual(sorted(order), sorted(self._codes()), f"{rater} lost/duplicated codes")

    def test_raters_get_different_orders(self):
        orders = brp.per_rater_orders(self._codes(), n_raters=4, seed=1)
        seqs = [tuple(o) for o in orders.values()]
        self.assertEqual(len(set(seqs)), len(seqs), "two raters share an order - not independent")

    def test_deterministic(self):
        self.assertEqual(
            brp.per_rater_orders(self._codes(), 3, seed=42),
            brp.per_rater_orders(self._codes(), 3, seed=42),
        )


class TestRenderRegisterTable(unittest.TestCase):
    def test_escapes_pipes_and_newlines(self):
        # A description containing '|' would otherwise break the markdown table.
        out = brp.render_register_table(
            {"risks": [{"description": "a|b\nc", "category": "schedule",
                        "likelihood": 3, "impact": 4, "mitigation": "m|n"}]}
        )
        body = out.splitlines()[2]
        self.assertIn(r"a\|b c", body)
        self.assertIn(r"m\|n", body)

    def test_empty_register_renders_placeholder_row(self):
        out = brp.render_register_table({"risks": []})
        self.assertIn("no parseable risks", out)

    def test_none_parsed_renders_placeholder(self):
        self.assertIn("no parseable risks", brp.render_register_table(None))


class TestBlindingIntegrity(unittest.TestCase):
    """The assertions that actually protect Method B's validity."""

    GT_SENTINEL = "GROUNDTRUTHSENTINEL_human_authored_register_row"
    PLANNING_SENTINEL = "PLANNINGSENTINEL_appraisal_document_body"
    GEN_SENTINEL = "GENSENTINEL_model_written_risk_description"

    def _fixture(self, tmp: Path):
        """Build a temp corpus: processed planning text, one raw output, and a
        ground-truth file that must never be touched."""
        processed = tmp / "processed"
        raw = tmp / "raw_outputs"
        gt = tmp / "ground_truth"
        for d in (processed, raw, gt):
            d.mkdir(parents=True, exist_ok=True)

        (processed / "P-UK-Alpha.txt").write_text(self.PLANNING_SENTINEL, encoding="utf-8")
        (gt / "P-UK-Alpha.json").write_text(
            json.dumps({"risks": [{"description": self.GT_SENTINEL}]}), encoding="utf-8")
        (raw / "P-UK-Alpha__claude__structured__run1.json").write_text(json.dumps({
            "parsed_risks": {"project_id": "P-UK-Alpha", "risks": [{
                "risk_id": "R01", "description": self.GEN_SENTINEL,
                "category": "schedule", "likelihood": 3, "impact": 4,
                "mitigation": "Stage the delivery.", "evidence": "Sec III",
            }]}
        }), encoding="utf-8")
        return processed, raw

    def _patched(self, processed: Path, raw: Path):
        def fake_raw_path(pid, model, prompt, run_index):
            return raw / f"{pid}__{model}__{prompt}__run{run_index}.json"
        return (mock.patch.object(brp, "PROCESSED_DIR", processed),
                mock.patch.object(brp, "raw_output_path", fake_raw_path))

    def test_packet_shows_planning_and_generated_register_but_not_ground_truth(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            processed, raw = self._fixture(tmp)
            p1, p2 = self._patched(processed, raw)
            reg = {"project_id": "P-UK-Alpha", "model": "claude",
                   "prompt_strategy": "structured", "run_index": 1, "code": "REG-001"}
            with p1, p2:
                md, status = brp.render_packet(reg)
            self.assertEqual(status, "rendered")
            self.assertIn(self.PLANNING_SENTINEL, md)   # rater needs the planning docs
            self.assertIn(self.GEN_SENTINEL, md)        # and the register under review
            self.assertNotIn(self.GT_SENTINEL, md)      # never the human answer key

    def test_packet_does_not_name_the_model_or_prompt_strategy(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            processed, raw = self._fixture(tmp)
            p1, p2 = self._patched(processed, raw)
            reg = {"project_id": "P-UK-Alpha", "model": "claude",
                   "prompt_strategy": "structured", "run_index": 1, "code": "REG-001"}
            with p1, p2:
                md, _ = brp.render_packet(reg)
            lowered = md.lower()
            for leak in list(brp.MODELS) + list(brp.PROMPTS):
                self.assertNotIn(leak, lowered, f"packet leaks {leak!r}")

    def test_missing_generation_is_pending_not_a_crash(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            processed, raw = self._fixture(tmp)
            p1, p2 = self._patched(processed, raw)
            reg = {"project_id": "P-UK-Alpha", "model": "gpt",
                   "prompt_strategy": "zero_shot", "run_index": 1, "code": "REG-002"}
            with p1, p2:
                md, status = brp.render_packet(reg)
            self.assertIsNone(md)
            self.assertEqual(status, "pending_generation")

    def test_parse_failed_generation_still_renders_a_packet(self):
        # A register that failed schema validation is a legitimate quality data
        # point for Method B - it must be rated, not skipped.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            processed, raw = self._fixture(tmp)
            (raw / "P-UK-Alpha__gpt__zero_shot__run1.json").write_text(
                json.dumps({"parsed_risks": None}), encoding="utf-8")
            p1, p2 = self._patched(processed, raw)
            reg = {"project_id": "P-UK-Alpha", "model": "gpt",
                   "prompt_strategy": "zero_shot", "run_index": 1, "code": "REG-002"}
            with p1, p2:
                md, status = brp.render_packet(reg)
            self.assertEqual(status, "rendered")
            self.assertIn("did not produce a schema-valid register", md)

    def test_shareable_outputs_contain_no_truth_but_blinding_map_does(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            processed, raw = self._fixture(tmp)
            out_dir = tmp / "out"
            regs = brp.assign_codes(brp.sample_cells(POOL, 5, 1, seed=3), seed=3)
            for r in regs:
                r["run_index"] = 1
            orders = brp.per_rater_orders([r["code"] for r in regs], 4, seed=3)
            p1, p2 = self._patched(processed, raw)
            with p1, p2:
                brp.write_outputs(regs, orders, {"seed": 3}, out_dir)

            # The blinding map IS the de-anonymizing key - it must carry truth.
            with (out_dir / "blinding_map.csv").open(encoding="utf-8") as f:
                map_rows = list(csv.DictReader(f))
            self.assertEqual(len(map_rows), len(regs))
            self.assertEqual(
                set(map_rows[0]),
                {"code", "project_id", "model", "prompt_strategy", "run_index", "cell"},
            )

            # Rater assignment sheets are shareable: opaque codes + blank scores only.
            for sheet in (out_dir / "rater_assignments").glob("*.csv"):
                text = sheet.read_text(encoding="utf-8")
                for leak in list(brp.MODELS) + list(brp.PROMPTS) + [r["project_id"] for r in regs]:
                    self.assertNotIn(leak, text, f"{sheet.name} leaks {leak!r}")
                with sheet.open(encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), len(regs))
                self.assertTrue(all(r["completeness_1to5"] == "" for r in rows))

    def test_packet_filenames_are_codes_only(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            processed, raw = self._fixture(tmp)
            out_dir = tmp / "out"
            regs = brp.assign_codes(brp.sample_cells(POOL, 5, 1, seed=3), seed=3)
            for r in regs:
                r["run_index"] = 1
            orders = brp.per_rater_orders([r["code"] for r in regs], 2, seed=3)
            p1, p2 = self._patched(processed, raw)
            with p1, p2:
                brp.write_outputs(regs, orders, {"seed": 3}, out_dir)
            for packet in (out_dir / "packets").glob("*"):
                self.assertRegex(packet.name, r"^REG-\d{3}\.md$")


class TestNeverReadsGroundTruth(unittest.TestCase):
    def test_source_does_not_reference_the_ground_truth_directory(self):
        # A static guard: this is the invariant most likely to be broken later
        # by someone "helpfully" showing raters the reference register.
        src = (SRC / "build_rater_packets.py").read_text(encoding="utf-8")
        code_lines = []
        in_docstring = False
        for line in src.splitlines():
            if line.count('"""') == 1:
                in_docstring = not in_docstring
                continue
            if in_docstring or line.lstrip().startswith("#"):
                continue
            code_lines.append(line)
        code = "\n".join(code_lines)
        self.assertNotIn("ground_truth", code)
        self.assertNotIn("risk_source_audit", code)


class TestEligiblePoolCanSatisfyTheDecidedSettings(unittest.TestCase):
    """Canary over the REAL manifest: the decided Method B settings
    (--sample-per-cell 5 --min-uk-per-cell 1) must remain satisfiable as the
    corpus changes. Asserts invariants, not a frozen corpus size."""

    def test_real_pool_supports_default_sampling(self):
        pool = brp.included_projects()
        uk = [p for p in pool if brp.is_uk(p)]
        self.assertGreaterEqual(len(pool), brp.DEFAULT_SAMPLE_PER_CELL)
        self.assertGreaterEqual(len(uk), 1, "no UK projects - --min-uk-per-cell 1 would raise")
        regs = brp.sample_cells(pool, brp.DEFAULT_SAMPLE_PER_CELL, 1, brp.DEFAULT_SEED)
        self.assertEqual(len(regs), N_CELLS * brp.DEFAULT_SAMPLE_PER_CELL)

    def test_every_sampled_project_has_processed_text(self):
        # render_packet falls back to "(planning text not found)" rather than
        # failing, so a missing file would silently produce a useless packet.
        pool = brp.included_projects()
        regs = brp.sample_cells(pool, brp.DEFAULT_SAMPLE_PER_CELL, 1, brp.DEFAULT_SEED)
        for pid in {r["project_id"] for r in regs}:
            self.assertTrue((brp.PROCESSED_DIR / f"{pid}.txt").exists(),
                            f"no processed text for sampled project {pid}")


if __name__ == "__main__":
    unittest.main()
