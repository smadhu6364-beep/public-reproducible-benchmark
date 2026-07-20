"""check_env.py - one-command connectivity check for the three model-API
paths, so it's possible to confirm every configured provider actually
authenticates BEFORE spending real money on a full grid run
(src/run_experiments.py).

Standalone - does not import or touch match.py, metrics.py,
run_experiments.py, or judge.py. Safe to run repeatedly: for each provider it
makes only the cheapest possible real request that still proves auth works
(a models-list / whoami call), never a real generation.

Usage:
  python src/check_env.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


def _load_env() -> None:
    from dotenv import load_dotenv

    # override=False: real shell-exported vars (e.g. in CI) still win over
    # whatever .env has, matching the usual dotenv convention.
    load_dotenv(ENV_PATH, override=False)


def check_anthropic() -> tuple[str, bool, str]:
    label = "Anthropic (Claude)"
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return (label, False, "not configured")
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        client.models.list(limit=1)
        return (label, True, "OK")
    except Exception as e:  # noqa: BLE001 - report and move on to the next provider
        return (label, True, f"FAIL: {e}")


def check_openai() -> tuple[str, bool, str]:
    label = "OpenAI (GPT)"
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return (label, False, "not configured")
    try:
        import openai

        client = openai.OpenAI(api_key=key)
        client.models.list()
        return (label, True, "OK")
    except Exception as e:  # noqa: BLE001
        return (label, True, f"FAIL: {e}")


def check_opensource() -> tuple[str, bool, str]:
    """Mirrors run_experiments.py's call_opensource() dispatch: whichever of
    the two documented access paths is configured in .env gets checked - a
    self-hosted OpenAI-compatible endpoint (OPENSOURCE_BASE_URL), or HF
    hosted inference (HF_TOKEN). Neither is assumed; it's an error condition
    (reported as "not configured", not a crash) if neither is set, same as
    run_experiments.py's own error message for this case.
    """
    label = "Open-source model"
    base_url = os.environ.get("OPENSOURCE_BASE_URL")
    opensource_key = os.environ.get("OPENSOURCE_API_KEY")
    hf_token = os.environ.get("HF_TOKEN")

    if base_url:
        label = f"Open-source (self-hosted endpoint: {base_url})"
        try:
            import openai

            client = openai.OpenAI(api_key=opensource_key or "unused", base_url=base_url)
            client.models.list()
            return (label, True, "OK")
        except Exception as e:  # noqa: BLE001
            return (label, True, f"FAIL: {e}")
    elif hf_token:
        label = "Open-source (HF hosted inference)"
        try:
            from huggingface_hub import HfApi

            who = HfApi().whoami(token=hf_token)
            username = who.get("name", "?") if isinstance(who, dict) else "?"
            return (f"{label}, user={username}", True, "OK")
        except ImportError:
            return (
                label,
                True,
                "FAIL: huggingface_hub not installed (it's a transitive dep of "
                "sentence-transformers here, not a direct one - add it to "
                "requirements.txt if HF hosted inference is the chosen path)",
            )
        except Exception as e:  # noqa: BLE001
            return (label, True, f"FAIL: {e}")
    else:
        return (
            label,
            False,
            "not configured (neither OPENSOURCE_BASE_URL nor HF_TOKEN set)",
        )


def main() -> int:
    if not ENV_PATH.exists():
        print(f"NOTE: {ENV_PATH} does not exist yet - copy .env.example to .env and fill in keys.\n", file=sys.stderr)
    _load_env()

    checks = [check_anthropic(), check_openai(), check_opensource()]

    name_width = max(len(name) for name, _, _ in checks)
    print(f"{'PROVIDER':<{name_width}}  {'CONFIGURED':<11}  RESULT")
    print("-" * (name_width + 11 + 9))
    any_fail = False
    for name, configured, result in checks:
        if result.startswith("FAIL"):
            any_fail = True
        print(f"{name:<{name_width}}  {str(configured):<11}  {result}")

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
