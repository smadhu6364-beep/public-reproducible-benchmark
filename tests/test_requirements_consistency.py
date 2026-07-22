"""Guards requirements.txt against drifting from what src/ and analysis/
actually import.

Task F7. Two directions, both real drift risks:
  1. every third-party top-level import used in src/ or analysis/ has a
     pinned line in requirements.txt (so a fresh `pip install -r
     requirements.txt` doesn't leave someone hitting ImportError mid-run);
  2. every pinned package is actually imported somewhere in src/ or
     analysis/ (no stale/unused pins quietly bloating the dependency list).

Both directions have narrow, explicitly-documented exceptions below -
conditional imports and CLAUDE.md-approved-but-not-yet-used libraries -
rather than a blanket escape hatch. Adding to either exception set should
require the same kind of real citation already present here, mirroring
tests/test_show_path_helper.py's ALLOWED-set convention.

Run: python -m unittest discover -s tests
"""

import ast
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
ANALYSIS = REPO / "analysis"
REQUIREMENTS = REPO / "requirements.txt"

# Import name -> PyPI package name, for the cases where they genuinely
# differ (most packages' import name already matches, modulo hyphen vs
# underscore, which is handled separately below).
IMPORT_TO_PACKAGE = {
    "fitz": "pymupdf",  # PyMuPDF's import name is `fitz`, not `pymupdf`.
    "dotenv": "python-dotenv",
}

# Third-party imports that are conditional/optional at the call site, with
# the reasoning already documented inline in the source - deliberately NOT
# pinned. Verified 2026-07-22: both call sites below say so explicitly.
KNOWN_OPTIONAL_UNPINNED_IMPORTS = {
    "huggingface_hub": (
        "Conditional HF-hosted-inference path: imported inside `elif "
        "hf_token:` in run_experiments.py's call_opensource(), and inside "
        "a try/except ImportError in check_env.py's open-source check. "
        "Both sites say inline this is deliberately unpinned unless that "
        "path is chosen. It wasn't: DECIDED 2026-07-21 (Madhu) was the "
        "Together AI base-URL path instead (see .env's OPENSOURCE_BASE_URL "
        "and docs/opensource_slot_options.md). This branch stays live code "
        "for flexibility, just not the configured path - add "
        "huggingface_hub to requirements.txt only if that path is ever "
        "actually chosen instead."
    ),
}

# RESOLVED 2026-07-22 (Madhu): pandas and scikit-learn were both flagged
# here as pinned-but-unused (named in CLAUDE.md's approved library list,
# but no src/ or analysis/ script actually imported either - match.py's
# cosine similarity uses numpy directly, _cosine_matrix()). Madhu's call was
# to drop both pins rather than keep them for speculative future use - see
# requirements.txt. This allowlist is intentionally empty now; if a future
# CLAUDE.md-approved library is pinned before anything imports it, add an
# entry here with the same kind of citation the pandas/scikit-learn entries
# used to have, don't silently widen test_no_stale_unused_pin's tolerance.
KNOWN_UNUSED_BUT_CLAUDE_MD_APPROVED: dict[str, str] = {}

STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}


def _local_module_names() -> set[str]:
    """Filenames (minus .py) of first-party modules living in src/ or
    analysis/ - these import each other directly and should never be
    expected to appear in requirements.txt."""
    return {f.stem for f in list(SRC.glob("*.py")) + list(ANALYSIS.glob("*.py"))}


def _top_level_imports() -> set[str]:
    """Every top-level third-party import name used anywhere in src/ or
    analysis/, via ast (not regex) so `import x as y` / `from x.y import z`
    / multi-import lines are all handled correctly."""
    local = _local_module_names()
    names: set[str] = set()
    for f in list(SRC.glob("*.py")) + list(ANALYSIS.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    names.add(node.module.split(".")[0])
    return names - STDLIB - local - set(KNOWN_OPTIONAL_UNPINNED_IMPORTS)


def _expected_package_name(import_name: str) -> str:
    if import_name in IMPORT_TO_PACKAGE:
        return IMPORT_TO_PACKAGE[import_name]
    return import_name.replace("_", "-")


def _pinned_packages() -> set[str]:
    """Lowercased package names from requirements.txt (before `==`),
    skipping blank lines and comments."""
    pkgs = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==")[0].strip()
        if name:
            pkgs.add(name.lower())
    return pkgs


class TestRequirementsMatchActualImports(unittest.TestCase):
    def test_every_third_party_import_is_pinned(self):
        pinned = _pinned_packages()
        used = _top_level_imports()
        missing = sorted(
            imp for imp in used
            if _expected_package_name(imp).lower() not in pinned
        )
        self.assertEqual(
            missing, [],
            f"requirements.txt is missing a pin for: {missing} (imported in "
            f"src/ or analysis/ but not found, under the expected package "
            f"name, in requirements.txt). If this is a genuinely new "
            f"dependency, CLAUDE.md requires asking before adding it - if "
            f"it's conditional/optional, add it to "
            f"KNOWN_OPTIONAL_UNPINNED_IMPORTS with the same kind of citation "
            f"already there for huggingface_hub."
        )

    def test_no_stale_unused_pin(self):
        pinned = _pinned_packages()
        used = _top_level_imports()
        used_packages = {_expected_package_name(imp).lower() for imp in used}
        approved_unused = {k.lower() for k in KNOWN_UNUSED_BUT_CLAUDE_MD_APPROVED}
        unused = sorted(pinned - used_packages - approved_unused)
        self.assertEqual(
            unused, [],
            f"requirements.txt pins packages not imported anywhere in src/ "
            f"or analysis/: {unused}. Either something lost a reference "
            f"(check for a typo/rename), or the pin is genuinely stale and "
            f"should be removed, or it's approved-but-not-yet-used and "
            f"belongs in KNOWN_UNUSED_BUT_CLAUDE_MD_APPROVED with a citation."
        )

    def test_known_optional_imports_still_actually_appear_unpinned(self):
        # If huggingface_hub ever gets added to requirements.txt (e.g. the
        # HF-hosted path gets chosen after all), this allowlist entry
        # becomes stale and should be deleted, not left dangling.
        pinned = _pinned_packages()
        for import_name in KNOWN_OPTIONAL_UNPINNED_IMPORTS:
            expected_pkg = _expected_package_name(import_name).lower()
            self.assertNotIn(
                expected_pkg, pinned,
                f"{import_name!r} is now pinned in requirements.txt but is "
                f"still listed in KNOWN_OPTIONAL_UNPINNED_IMPORTS as "
                f"deliberately unpinned - remove it from that allowlist, "
                f"it's no longer an exception."
            )

    def test_known_unused_approved_libraries_are_still_actually_unused(self):
        # Mirror check: if pandas/scikit-learn start being imported, this
        # allowlist entry becomes stale and should be deleted so the real
        # test (test_no_stale_unused_pin) starts covering it again.
        used = _top_level_imports()
        used_packages = {_expected_package_name(imp).lower() for imp in used}
        for pkg_name in KNOWN_UNUSED_BUT_CLAUDE_MD_APPROVED:
            self.assertNotIn(
                pkg_name.lower(), used_packages,
                f"{pkg_name!r} is now actually imported in src/ or "
                f"analysis/ but is still listed in "
                f"KNOWN_UNUSED_BUT_CLAUDE_MD_APPROVED as unused - remove it "
                f"from that allowlist, it's no longer a gap."
            )


if __name__ == "__main__":
    unittest.main()
