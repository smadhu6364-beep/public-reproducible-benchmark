"""check_env.py - one-command connectivity check for the three model-API
paths, so it's possible to confirm every configured provider actually
authenticates BEFORE running a real grid (src/run_experiments.py).

REDESIGNED 2026-07-23 (Madhu, budget-driven), then REDESIGNED AGAIN
2026-07-23 (later the same day): the originally-decided paid triple
(Anthropic Claude / OpenAI GPT / Together AI Llama) all hit real
billing/quota errors on the first actual spend attempt, so all 3 slots moved
to free-tier providers (Google Gemini + Groq). Groq's free tier then turned
out to have a hard 8,000 TPM per-request cap that this project's real
~30-34K-token prompts exceed ~4x - not fixable by retry/pacing - so the
"gpt" and "opensource" slots moved again, to SambaNova Cloud. See PROJECT_SPEC.md's
RQ2 correction note, docs/model_tier_recommendation.md's dated addenda, and
run_experiments.py's call_claude/call_gpt/call_opensource docstrings for
exactly what each slot calls now.

Standalone - does not import or touch match.py, metrics.py,
run_experiments.py, or judge.py. Safe to run repeatedly: for each provider it
hits only the cheapest possible real request that still proves auth works
(an authenticated GET against the provider's /models endpoint), never a real
generation.

Usage:
  python src/check_env.py
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
SAMBANOVA_BASE_URL = "https://api.sambanova.ai/v1/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _load_env() -> None:
    from dotenv import load_dotenv

    # override=False: real shell-exported vars (e.g. in CI) still win over
    # whatever .env has, matching the usual dotenv convention.
    load_dotenv(ENV_PATH, override=False)


def _check_openai_compatible_endpoint(label: str, base_url: str, api_key: str) -> tuple[str, bool, str]:
    """Shared check for any OpenAI-compatible /models endpoint - status code
    only, deliberately NEVER parsed via the openai SDK's response-model
    parsing. Found 2026-07-23, on the first real call ever made against a
    live third-party OpenAI-compatible endpoint: Together AI's /v1/models
    returned a bare JSON list (no {"object": "list", "data": [...]}
    wrapper), which crashed the SDK's response parsing with a confusing,
    non-auth-looking error ("'list' object has no attribute
    '_set_private_attributes'") - looked like a broken key, wasn't one. A
    bare urllib request (Python's default User-Agent) separately got a 403
    from something in front of that same endpoint. Both problems are
    avoided here: hit /models directly with an explicit User-Agent and
    check only the HTTP status, never the body shape - this also means one
    function works for any OpenAI-compatible provider regardless of that
    provider's specific /models response format.
    """
    req = urllib.request.Request(
        base_url.rstrip("/") + "/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "llm-risk-register-benchmark/check_env.py",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20):
            return (label, True, "OK")
    except urllib.error.HTTPError as e:
        return (label, True, f"FAIL: HTTP {e.code} {e.reason}")
    except Exception as e:  # noqa: BLE001 - report and move on to the next provider
        return (label, True, f"FAIL: {e}")


def check_claude_slot() -> tuple[str, bool, str]:
    """Checks the "claude" MODEL_DISPATCH slot's actually-configured
    provider - Google Gemini via its documented OpenAI-compatible endpoint
    as of the 2026-07-23 free-tier redesign (see run_experiments.py's
    call_claude()). The slot name is kept for continuity even though it no
    longer calls Anthropic."""
    label = "Gemini (claude slot)"
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return (label, False, "not configured")
    return _check_openai_compatible_endpoint(label, GEMINI_BASE_URL, key)


def check_gpt_slot() -> tuple[str, bool, str]:
    """Checks the "gpt" MODEL_DISPATCH slot - SambaNova Cloud serving
    openai/gpt-oss-120b as of the second 2026-07-23 redesign (Groq's free
    tier couldn't serve this project's real prompt sizes - see
    run_experiments.py's call_gpt())."""
    label = "SambaNova (gpt slot)"
    key = os.environ.get("SAMBANOVA_API_KEY")
    if not key:
        return (label, False, "not configured")
    return _check_openai_compatible_endpoint(label, SAMBANOVA_BASE_URL, key)


def check_opensource_slot() -> tuple[str, bool, str]:
    """Checks the "opensource" MODEL_DISPATCH slot - SambaNova Cloud serving
    Meta-Llama-3.3-70B-Instruct as of the second 2026-07-23 redesign (see
    run_experiments.py's call_opensource()). Same SambaNova account/key as
    the "gpt" slot above (SAMBANOVA_API_KEY is shared) - this check is
    redundant with it in practice, but kept as its own function so
    check_env.py's output still maps 1:1 onto the 3 real MODEL_DISPATCH
    slots, same as before this redesign."""
    label = "SambaNova (opensource slot)"
    key = os.environ.get("SAMBANOVA_API_KEY")
    if not key:
        return (label, False, "not configured")
    return _check_openai_compatible_endpoint(label, SAMBANOVA_BASE_URL, key)


def check_openrouter_supplemental() -> tuple[str, bool, str]:
    """OPTIONAL, ADDED 2026-07-25: OpenRouter is a supplemental provider for
    the gpt/opensource slots (see run_experiments.py's OPENROUTER_MODEL_ID
    comment), tried only after SambaNova returns a transient error - not one
    of the 3 required MODEL_DISPATCH slots, so an unconfigured or failing
    OpenRouter key does NOT flip check_env.py's exit code (unlike the 3
    checks above)."""
    label = "OpenRouter (gpt/opensource supplemental)"
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return (label, False, "not configured (optional)")
    return _check_openai_compatible_endpoint(label, OPENROUTER_BASE_URL, key)


def main() -> int:
    if not ENV_PATH.exists():
        print(f"NOTE: {ENV_PATH} does not exist yet - copy .env.example to .env and fill in keys.\n", file=sys.stderr)
    _load_env()

    checks = [check_claude_slot(), check_gpt_slot(), check_opensource_slot()]
    supplemental = check_openrouter_supplemental()

    name_width = max(len(name) for name, _, _ in checks + [supplemental])
    print(f"{'PROVIDER':<{name_width}}  {'CONFIGURED':<11}  RESULT")
    print("-" * (name_width + 11 + 9))
    any_fail = False
    for name, configured, result in checks:
        if result.startswith("FAIL"):
            any_fail = True
        print(f"{name:<{name_width}}  {str(configured):<11}  {result}")
    sup_name, sup_configured, sup_result = supplemental
    print(f"{sup_name:<{name_width}}  {str(sup_configured):<11}  {sup_result}")

    if any_fail:
        print("\nAt least one configured provider failed to authenticate - see FAIL messages above.", file=sys.stderr)
        return 1
    if not any(configured for _, configured, _ in checks):
        print("\nNo provider is configured yet - nothing to check. Fill in .env first.", file=sys.stderr)
        return 0
    print("\nAll configured providers authenticated OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
