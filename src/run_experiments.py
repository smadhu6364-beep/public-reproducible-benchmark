"""run_experiments.py - drive the 3 models x 3 prompts x ~20 projects grid.

IMPLEMENTED 2026-07-19 with explicit user approval, after the project's own
10-document ground-truth validation gate was crossed (18/18 non-set-aside
documents). NOTE: this file is code-complete but CANNOT be run for a real
experiment yet - .env has no real API keys configured as of this writing.
The model-tier decision this note originally flagged as open (which tier of
each of the 3 models to benchmark, a research-design/scope decision per
CLAUDE.md, deliberately not picked in this file) is RESOLVED as of
2026-07-21 (Madhu) - all three are decided and pre-filled in .env.example
(Claude Sonnet 5 intro pricing, GPT-5.6 Terra, Llama 3.3 70B Turbo via
Together AI; see docs/model_tier_recommendation.md and
docs/opensource_slot_options.md). The only remaining blocker is real API
keys themselves - copy .env.example to .env and fill in
ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENSOURCE_API_KEY; the script raises a
clear error rather than silently defaulting if any of the *_MODEL_NAME vars
are unset at run time, but that should no longer happen from a fresh
.env.example copy.

Responsibilities:
  - Load processed planning text per project (data/processed/) - NEVER reads
    data/ground_truth/ or data/risk_source_audit/ for any project; see the
    LEAKAGE GUARD section below for the runtime check that enforces this.
  - For each (model, prompt, project, run): call the model at temperature
    0-0.2, write raw output to results/raw_outputs/ (append-only - a run that
    already exists is never overwritten; use --runs N to request N runs per
    combination and the script assigns the next free run_index per combo),
    and append {model_version, run_date, temperature, prompt_sha256} plus
    identifying fields to results/run_config.jsonl.
  - Cost guard: before making ANY API call for a requested grid, estimate
    total token usage x per-model pricing, print the estimate, and refuse to
    proceed without --confirm-cost if the estimate exceeds $30 (CLAUDE.md
    cost-guard rule). Use --estimate-only to print the estimate and exit
    without calling any API regardless of size.
  - ADDED 2026-07-21 (Madhu's decision: build batch support, then run 2 at
    the cheaper rate - "2-3 runs each" and "$30 guard" conflict at
    synchronous pricing, see results/preflight_report.md §2): --batch
    submits claude+gpt cells to Anthropic's and OpenAI's batch APIs (~50%
    off list) instead of calling synchronously, then exits immediately
    without waiting - batch jobs can take up to 24h. opensource/Together AI
    stays on the synchronous path (its batch-discount availability was never
    verified - see submit_batch_grid's docstring). Run --batch-check
    afterward, any number of times, to poll and collect finished results,
    written through the exact same _finalize_run() path a synchronous run
    uses so match.py/metrics.py/judge.py/build_rater_packets.py need no
    changes. Real SDK method/field names were confirmed against the actually
    installed anthropic==0.117.0 / openai==1.109.1 packages, but the
    submit/check cycle itself has only been exercised against mocked
    clients (see tests/test_batch.py) - no OPENAI_API_KEY or ANTHROPIC batch
    call has ever been made for this project. Verify results/batch_jobs.json
    and the first few batch-sourced raw_outputs records by hand the first
    time this runs for real, the same way call_gpt's temperature-retry path
    is flagged for first-real-call verification.

REDESIGNED 2026-07-23 (Madhu, budget-driven): the paid triple described
above (Anthropic/OpenAI/Together AI) all hit real billing/quota errors on
the first actual spend attempt. The model lineup is now 3 genuinely
free-tier models via Google Gemini and Groq - see CLAUDE.md's RQ2
correction note, docs/model_tier_recommendation.md's dated addendum, and
call_claude/call_gpt/call_opensource's own docstrings below for exactly
what each slot calls now. **--batch/--batch-check are now INAPPLICABLE,
not just unnecessary:** they submit to Anthropic's and OpenAI's native
batch APIs specifically (submit_claude_batch/submit_gpt_batch,
BATCH_ELIGIBLE_LABELS below), which the new Gemini/Groq OpenAI-compatible
endpoints are not wired for and were never verified to support. Since every
slot is now free, there is also no cost discount left to batch for - use
the plain synchronous path (no --batch flag) for a real run; --confirm-cost
should never be needed either, since the estimate is genuinely $0.00. The
batch code path itself is left in place, untouched, rather than deleted -
it remains real, tested (tests/test_batch.py), and would still work if a
future funded run ever reverts to paid Anthropic/OpenAI accounts.

Known limitations, stated plainly:
  - Token estimation is a char-count heuristic (~4 chars/token), not a real
    tokenizer - Anthropic's own pricing FAQ describes this as "a rough
    estimate" too, so this is consistent with how Anthropic itself frames it,
    but it is still an approximation. Treat COST ESTIMATES as directionally
    useful, not penny-accurate, and re-check against the provider console
    after the first small batch of real calls.
  - PRICING below for Anthropic models was fetched directly from
    platform.claude.com/docs/en/about-claude/pricing on 2026-07-19 and should
    be reliable as of that date. OpenAI pricing was gathered from a web search
    summary (not a direct fetch of platform docs) on the same date - treat it
    as lower-confidence and re-verify at developers.openai.com/api/docs/pricing
    before trusting a real cost estimate against it. Open-source model pricing
    is entirely dependent on which access path is chosen (HF hosted inference
    has its own per-token pricing; a self-hosted endpoint has no per-token API
    cost but has compute cost this script cannot see) - there is no default;
    set OPENSOURCE_PRICE_INPUT_PER_MTOK / OPENSOURCE_PRICE_OUTPUT_PER_MTOK in
    .env if the chosen path bills per token, or leave at 0 and track compute
    cost separately if self-hosted.
  - Pricing tables go stale. Whoever runs the real grid should re-check the
    numbers below against the provider's current pricing page first,
    especially if more than a few weeks have passed since 2026-07-19.
  - ADDED 2026-07-21, sourced via web search (not yet exercised against a
    real call - .env has never had a real OPENAI_API_KEY): OpenAI's GPT-5
    "reasoning" family, plausibly including gpt-5.6-terra (the model this
    project selected), is documented to reject the legacy `max_tokens` chat
    completions parameter (now `max_completion_tokens`) and to reject
    `temperature` outright when reasoning_effort != "none". call_gpt() below
    now sends max_completion_tokens unconditionally and defensively retries
    without temperature if the API specifically rejects it, recording the
    outcome as a `temperature_applied` field on every raw output record and
    run_config.jsonl line rather than silently proceeding as if CLAUDE.md's
    "temperature 0-0.2 across all 3 models" held when it might not have for
    the GPT slot. Verified so far only via a mocked openai.OpenAI client
    (three scenarios: normal success, temperature-rejected retry, an
    unrelated 400 propagating uncaught) - CONFIRM against a real call the
    first time real keys exist, and check run_config.jsonl's
    temperature_applied field across the first few GPT runs before trusting
    it silently. See the paper draft's Limitations section (V.A) for the
    disclosed methodological consequence if this fires for real.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
GROUND_TRUTH_DIR = REPO_ROOT / "data" / "ground_truth"
RISK_AUDIT_DIR = REPO_ROOT / "data" / "risk_source_audit"
PROMPTS_DIR = REPO_ROOT / "prompts"
RAW_OUTPUTS_DIR = REPO_ROOT / "results" / "raw_outputs"
RUN_CONFIG_LOG = REPO_ROOT / "results" / "run_config.jsonl"
MANIFEST_PATH = REPO_ROOT / "data" / "corpus_manifest.csv"
OUTPUT_SCHEMA_PATH = PROMPTS_DIR / "output_schema.json"
BATCH_JOBS_LOG = REPO_ROOT / "results" / "batch_jobs.json"


def _load_env() -> None:
    """Load .env into os.environ before anything below reads it.

    Found 2026-07-23, on the first real attempt to run this script after all
    three API keys were actually filled into .env: python-dotenv does NOT
    auto-load on import, and this module - unlike check_env.py, which has its
    own _load_env() - never called load_dotenv() anywhere. Every call_*/
    estimate_cost() function reads os.environ.get(...) directly, so without
    this, CLAUDE_MODEL_NAME/GPT_MODEL_NAME/all three API keys were silently
    absent from os.environ for any plain `python src/run_experiments.py`
    invocation - not a crash, a SILENT one: --estimate-only reported
    models_missing_pricing_data and a $0.00 estimate instead of erroring
    loudly, which is exactly the dangerous-looking-safe failure mode
    test_run_pipeline.py's test_unpriced_model_is_reported_not_silently_zero
    already guards against for a wrong model name - this was the same
    symptom, different cause (a missing load step, not a bad name). A real
    grid run in this state would have failed immediately once it tried to
    actually call a provider with an empty API key. Only called from main()
    (not at module import time) so importing this module for tests never
    triggers a real .env read - same convention check_env.py already uses,
    and why tests patch this to a no-op rather than relying on override=False
    alone to stay hermetic.
    """
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env", override=False)

# Providers whose batch endpoints are used by --batch. Both offer a
# documented ~50% discount vs. the synchronous price. opensource/Together AI
# is deliberately excluded: its batch-discount availability was never
# verified (see submit_batch_grid's docstring), so that slot always runs
# synchronously at list price regardless of --batch.
#
# INAPPLICABLE as of the 2026-07-23 free-tier redesign (see module
# docstring): "claude"/"gpt" now call Gemini/Groq, neither of which this
# batch path is wired for. Left as-is (not emptied/removed) since it's real,
# tested code that would still work if a funded run ever reverts to paid
# Anthropic/OpenAI accounts - just don't pass --batch against the current
# free-tier .env, it will fail on GEMINI_API_KEY/GROQ_API_KEY not being the
# ANTHROPIC_API_KEY/OPENAI_API_KEY this path still explicitly requires.
BATCH_ELIGIBLE_LABELS = frozenset({"claude", "gpt"})

PROMPT_FILES = {
    "zero_shot": PROMPTS_DIR / "zero_shot.txt",
    "few_shot": PROMPTS_DIR / "few_shot.txt",
    "structured": PROMPTS_DIR / "structured.txt",
}

DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.1  # within CLAUDE.md's required 0-0.2 range
COST_GUARD_THRESHOLD_USD = 30.0

# ADDED 2026-07-21: a 189-378-cell grid at real spend shouldn't need a human
# to notice and manually re-run one flaky timeout/rate-limit/5xx - see
# _is_transient_provider_error/_call_model_with_retry below. 3 total attempts
# (1 initial + 2 retries), exponential backoff (1s, then 2s).
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0

# --- Pricing, USD per million tokens (input, output). See module docstring
# for sourcing/confidence notes. Keyed by the exact model ID string so the
# script can price whichever specific model the .env config points at.
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    # REDESIGNED 2026-07-23 (Madhu, budget-driven - all 3 provider accounts
    # hit real billing/quota errors on the first actual spend attempt; see
    # CLAUDE.md's RQ2 correction note and docs/model_tier_recommendation.md's
    # dated addendum). The three models actually configured now are genuinely
    # free-tier - $0.00 per token is a real fact about these endpoints, not a
    # missing-data placeholder. Re-verify if free-tier terms ever change.
    "gemini-2.5-flash": (0.0, 0.0),        # Google AI Studio free tier, no card
    "openai/gpt-oss-120b": (0.0, 0.0),     # Groq free tier, no card
    "qwen/qwen3.6-27b": (0.0, 0.0),        # Groq free tier, no card (shares Groq's daily quota with the row above)

    # Retained for reference only - NOT currently configured in .env.example,
    # since the paid Anthropic/OpenAI slots this project originally decided on
    # (docs/model_tier_recommendation.md) required real billing this project's
    # accounts didn't have. Real prices as fetched 2026-07-19; harmless to
    # leave here if a future funded run reverts to them.
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),  # introductory rate through 2026-08-31
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.6-sol": (5.00, 30.00),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-nano": (0.20, 1.25),
}


def _chars_to_tokens(n_chars: int) -> float:
    """Rough ~4 chars/token heuristic - see module docstring caveat."""
    return n_chars / 4.0


# ---------------------------------------------------------------------------
# Leakage guard
# ---------------------------------------------------------------------------

def assert_no_ground_truth_leakage() -> None:
    """Defense-in-depth static check, run once at startup.

    This module's prompt-construction code only ever opens files under
    PROCESSED_DIR by construction - grep the source of this file for any
    reference to GROUND_TRUTH_DIR or RISK_AUDIT_DIR being *read* (writing is
    fine; this script never writes there either, but the check is about
    reads). This function additionally guards against the few-shot template
    being edited in the future to reference a real corpus project instead of
    the synthetic EXAMPLE it currently uses.
    """
    import csv

    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        real_project_ids = {row["project_id"] for row in csv.DictReader(f)}

    few_shot_text = PROMPT_FILES["few_shot"].read_text(encoding="utf-8")
    for pid in real_project_ids:
        if pid in few_shot_text:
            raise RuntimeError(
                f"LEAKAGE GUARD TRIPPED: prompts/few_shot.txt appears to reference "
                f"real corpus project {pid!r}. The few-shot example MUST be a "
                f"synthetic exemplar never drawn from this study's corpus (see "
                f"CLAUDE.md leakage rule). Refusing to proceed."
            )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def load_planning_text(project_id: str) -> str:
    path = PROCESSED_DIR / f"{project_id}.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"No processed planning text for {project_id!r} at {path}. "
            f"Run `python3 src/extract.py --all` first."
        )
    return path.read_text(encoding="utf-8")


def render_prompt(prompt_strategy: str, project_id: str) -> str:
    if prompt_strategy not in PROMPT_FILES:
        raise ValueError(f"Unknown prompt_strategy {prompt_strategy!r}; expected one of {list(PROMPT_FILES)}")
    template = PROMPT_FILES[prompt_strategy].read_text(encoding="utf-8")
    planning_text = load_planning_text(project_id)
    return template.replace("{{PROJECT_ID}}", project_id).replace("{{PLANNING_DOCUMENT}}", planning_text)


def prompt_file_sha256(prompt_strategy: str) -> str:
    data = PROMPT_FILES[prompt_strategy].read_bytes()
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Model calls - one thin wrapper per provider. Each returns raw response text.
# ---------------------------------------------------------------------------

def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set in .env. Copy .env.example to .env and fill it "
            f"in (see .env.example for the exact variable names expected)."
        )
    return value


def _openai_compatible_call(
    base_url: str, api_key: str, model_version: str, prompt: str, temperature: float, max_tokens: int
) -> tuple[str, bool]:
    """Shared implementation for all 3 free-tier slots below - each is called
    through an OpenAI-compatible /chat/completions endpoint (Google's Gemini
    API documents its own such endpoint; Groq's is the same shape this
    project's original opensource slot already used for Together AI), so one
    real function replaces 3 near-duplicates rather than copy-pasting the
    request/response handling three times."""
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model_version,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or "", True


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def call_claude(prompt: str, model_version: str, temperature: float, max_tokens: int) -> tuple[str, bool]:
    """Returns (response_text, temperature_applied).

    REDESIGNED 2026-07-23 (Madhu, budget-driven - see CLAUDE.md's RQ2
    correction note and docs/model_tier_recommendation.md's dated addendum):
    the "claude" slot now calls Google's Gemini API via its documented
    OpenAI-compatibility endpoint (ai.google.dev/gemini-api/docs/openai), not
    Anthropic's Claude API - the original paid Claude slot required real
    account billing this project did not have. GEMINI_API_KEY replaces
    ANTHROPIC_API_KEY for this slot. The "claude" MODEL_DISPATCH key name is
    kept as-is (an internal role label used throughout metrics.py, tests, and
    rater packets - renaming it would be pure churn with no behavior change)
    even though it no longer calls Anthropic.

    No known temperature restriction on this endpoint, so temperature_applied
    is always True - unverified against a real call at the time of this
    rewrite; re-check results/run_config.jsonl's temperature_applied field on
    the first real run.
    """
    api_key = _require_env("GEMINI_API_KEY")
    return _openai_compatible_call(GEMINI_BASE_URL, api_key, model_version, prompt, temperature, max_tokens)


def call_gpt(prompt: str, model_version: str, temperature: float, max_tokens: int) -> tuple[str, bool]:
    """Returns (response_text, temperature_applied).

    REDESIGNED 2026-07-23 (Madhu, budget-driven): the "gpt" slot now calls
    Groq's free tier serving `openai/gpt-oss-120b` - OpenAI's own open-weight
    model family, served by a third party, not OpenAI's paid API, which
    required real billing this project did not have. GROQ_API_KEY replaces
    OPENAI_API_KEY for this slot.

    The previous version of this function had GPT-5-Terra-specific
    temperature-rejection/max_completion_tokens handling (that model's
    reasoning mode was documented to reject `temperature` outright). REMOVED
    here, not just left dormant: gpt-oss served via Groq is a different model
    family on a different serving stack, was never sourced to share that
    constraint, and speculative handling for a combination this was never
    verified against is worse than the plain path below. If a real call ever
    demonstrates an equivalent rejection, re-add equivalent handling then,
    sourced against the actual error.
    """
    api_key = _require_env("GROQ_API_KEY")
    return _openai_compatible_call(GROQ_BASE_URL, api_key, model_version, prompt, temperature, max_tokens)


def call_opensource(prompt: str, model_version: str, temperature: float, max_tokens: int) -> tuple[str, bool]:
    """Returns (response_text, temperature_applied).

    REDESIGNED 2026-07-23 (Madhu, budget-driven): the "opensource" slot now
    calls Groq's free tier serving a second, distinct open-weight model
    (Qwen, by default - see .env.example) - Together AI required real
    billing this project did not have. GROQ_API_KEY (shared with the "gpt"
    slot above - same Groq account, different model name) replaces
    OPENSOURCE_API_KEY/OPENSOURCE_BASE_URL. The HF-hosted-inference path
    (HF_TOKEN) is retired, not just left dormant - the decided access path
    is exclusively Gemini + Groq now; see git history before this commit if
    HF hosted inference is ever reconsidered.
    """
    api_key = _require_env("GROQ_API_KEY")
    return _openai_compatible_call(GROQ_BASE_URL, api_key, model_version, prompt, temperature, max_tokens)


MODEL_DISPATCH = {
    "claude": call_claude,
    "gpt": call_gpt,
    "opensource": call_opensource,
}


def _is_transient_provider_error(exc: BaseException) -> bool:
    """True for network-level/rate-limit/server-side errors worth retrying;
    False for anything retrying cannot fix (bad request, auth failure, a
    missing .env key via _require_env's RuntimeError, an unconfigured
    opensource path, etc.) - retrying one of those just wastes time and
    money and delays surfacing a real setup problem across a 189-378-cell
    grid.

    Duck-typed rather than importing anthropic/openai here: both are
    deferred imports inside call_claude/call_gpt/call_opensource
    specifically so this module has no hard dependency on either SDK being
    installed to do anything else, and both SDKs already follow a
    consistent, documented naming convention for these exception classes
    (RateLimitError, InternalServerError, APIConnectionError,
    APITimeoutError, each carrying a numeric status_code except the latter
    two, which represent a request that never got an HTTP response at all).
    """
    # 429 = rate limited, 5xx = the provider's own problem, not ours; every
    # other 4xx (400 bad request, 401 auth, 403 permission, 404 not found)
    # is deliberately NOT retried.
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code == 429 or status_code >= 500

    name = type(exc).__name__
    if any(marker in name for marker in
           ("RateLimitError", "InternalServerError", "APIConnectionError", "APITimeoutError")):
        return True
    return isinstance(exc, (ConnectionError, TimeoutError))


def _call_model_with_retry(model_label: str, prompt: str, model_version: str, temperature: float, max_tokens: int) -> tuple[str, bool]:
    """Wraps MODEL_DISPATCH[model_label] with up to RETRY_MAX_ATTEMPTS
    attempts and exponential backoff, but ONLY for errors
    _is_transient_provider_error recognizes. A non-transient error (bad
    request, auth failure, missing .env key, an unconfigured opensource
    path) is re-raised immediately on its FIRST occurrence, at whatever
    attempt it happens - there is no reason to wait and retry a call that
    cannot succeed."""
    fn = MODEL_DISPATCH[model_label]
    last_exc: BaseException | None = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            return fn(prompt, model_version, temperature, max_tokens)
        except Exception as e:
            if not _is_transient_provider_error(e):
                raise
            last_exc = e
            if attempt < RETRY_MAX_ATTEMPTS - 1:
                delay = RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                print(
                    f"[{model_label}] transient error on attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS} "
                    f"({type(e).__name__}: {e}) - retrying in {delay:.0f}s.",
                    file=sys.stderr,
                )
                time.sleep(delay)
    assert last_exc is not None  # loop above always assigns it before falling through
    raise last_exc


def resolve_model_version(model_label: str) -> str:
    """model_label is the short 'claude' | 'gpt' | 'opensource' key; the exact
    API model string comes from .env, never a hardcoded default - which tier
    of each provider to benchmark is a research-design decision, see
    module docstring."""
    env_var = {
        "claude": "CLAUDE_MODEL_NAME",
        "gpt": "GPT_MODEL_NAME",
        "opensource": "OPENSOURCE_MODEL_NAME",
    }[model_label]
    return _require_env(env_var)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_FINAL_JSON_RE = re.compile(r"FINAL JSON:\s*(\{.*\})\s*\Z", re.DOTALL)
_BARE_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_model_response(raw_text: str, prompt_strategy: str) -> tuple[Optional[dict], Optional[str]]:
    """Returns (parsed_risks, parse_error). Exactly one is None.

    zero_shot/few_shot: expect the ENTIRE response to be a single JSON object.
    structured: expect 'REASONING: ...' followed by 'FINAL JSON: {...}';
    only the JSON after the FINAL JSON: marker is parsed and validated.
    """
    import jsonschema

    with open(OUTPUT_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    text = raw_text.strip()
    if prompt_strategy == "structured":
        m = _FINAL_JSON_RE.search(text)
        if not m:
            return None, "structured response missing a 'FINAL JSON:' marker followed by a JSON object"
        json_text = m.group(1)
    else:
        # Defensive: models sometimes wrap JSON in markdown fences despite
        # instructions not to. Strip fences if present, then require the
        # remainder to parse as JSON outright.
        fence_stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        json_text = fence_stripped

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as e:
        # Last-resort fallback: try to find the first {...} blob anywhere in
        # the text before giving up, since some models add stray prose.
        m2 = _BARE_JSON_RE.search(json_text)
        if not m2:
            return None, f"JSON parse failed and no JSON object found: {e}"
        try:
            parsed = json.loads(m2.group(0))
        except json.JSONDecodeError as e2:
            return None, f"JSON parse failed: {e2}"

    try:
        jsonschema.validate(instance=parsed, schema=schema)
    except jsonschema.ValidationError as e:
        return None, f"parsed JSON does not conform to output_schema.json: {e.message}"

    return parsed, None


# ---------------------------------------------------------------------------
# Raw output naming (append-only) - see match.py's _RAW_OUTPUT_NAME_RE, which
# this naming convention must stay in sync with.
# ---------------------------------------------------------------------------

def raw_output_path(project_id: str, model_label: str, prompt_strategy: str, run_index: int) -> Path:
    return RAW_OUTPUTS_DIR / f"{project_id}__{model_label}__{prompt_strategy}__run{run_index}.json"


def _reserved_batch_run_indices(project_id: str, model_label: str, prompt_strategy: str) -> set[int]:
    """run_indices already claimed by a batch job that has been submitted but
    not yet collected. These have no file on disk yet - a batch can take up to
    24h to finish - so a plain filesystem check in next_free_run_index() can't
    see them. Without this, submitting --batch twice for the same cell before
    running --batch-check would silently hand out run_index=1 to BOTH batches;
    whichever finishes and gets collected second would hit _finalize_run's
    FileExistsError guard and be silently discarded as "already_written" -
    a real provider call, paid for, whose result is thrown away with no error
    surfaced beyond a count. Reads BATCH_JOBS_LOG directly rather than via
    _load_batch_jobs() to avoid a forward-reference ordering dependency."""
    if not BATCH_JOBS_LOG.exists():
        return set()
    with open(BATCH_JOBS_LOG, encoding="utf-8") as f:
        jobs = json.load(f)
    reserved = set()
    for job in jobs:
        if job.get("status") == "collected":
            continue
        for u in job.get("units", []):
            if (u["project_id"] == project_id and u["model_label"] == model_label
                    and u["prompt_strategy"] == prompt_strategy):
                reserved.add(u["run_index"])
    return reserved


def next_free_run_index(project_id: str, model_label: str, prompt_strategy: str) -> int:
    """Append-only: never overwrite an existing run's file. Finds the lowest
    run_index >= 1 with no existing file AND not already reserved by a
    pending (submitted, not yet collected) batch job, so repeated invocations
    - synchronous or batch, in either order - accumulate runs rather than
    colliding."""
    reserved = _reserved_batch_run_indices(project_id, model_label, prompt_strategy)
    idx = 1
    while raw_output_path(project_id, model_label, prompt_strategy, idx).exists() or idx in reserved:
        idx += 1
    return idx


@dataclass
class GridCell:
    project_id: str
    model_label: str
    prompt_strategy: str


def estimate_cost(
    cells: list[GridCell],
    runs_per_cell: int,
    max_output_tokens: int,
    batch_labels: frozenset[str] = frozenset(),
) -> dict:
    """Estimate total cost across the requested grid before any API calls are
    made. See module docstring for the token-estimation and pricing caveats.

    batch_labels: model labels priced at the batch-API discount (both
    Anthropic and OpenAI publish ~50% off list for batch requests) instead of
    the synchronous rate. Pass BATCH_ELIGIBLE_LABELS from --batch's estimate
    so the cost guard evaluates against what will actually be spent, not the
    synchronous price of a run that was never going to be synchronous.
    Labels not in PRICING_PER_MTOK's per-provider discount (currently just
    opensource, which is never in BATCH_ELIGIBLE_LABELS) are unaffected even
    if passed here.
    """
    by_model: dict[str, dict] = {}
    total_usd = 0.0
    missing_pricing = set()

    for cell in cells:
        try:
            model_version = resolve_model_version(cell.model_label)
        except RuntimeError:
            model_version = f"<{cell.model_label} model not configured in .env>"
        prompt_text = render_prompt(cell.prompt_strategy, cell.project_id)
        input_tokens = _chars_to_tokens(len(prompt_text))
        output_tokens = max_output_tokens  # worst-case assumption, deliberately conservative

        pricing = PRICING_PER_MTOK.get(model_version)
        if pricing is None and cell.model_label == "opensource":
            # Fall back to the env-configured open-source price (default 0,
            # e.g. for a self-hosted endpoint with no per-token API cost -
            # see .env.example note on OPENSOURCE_PRICE_INPUT_PER_MTOK).
            try:
                pricing = (
                    float(os.environ.get("OPENSOURCE_PRICE_INPUT_PER_MTOK", 0)),
                    float(os.environ.get("OPENSOURCE_PRICE_OUTPUT_PER_MTOK", 0)),
                )
            except ValueError:
                pricing = None
        if pricing is None:
            missing_pricing.add(model_version)
            cell_cost = 0.0
        else:
            in_price, out_price = pricing
            if cell.model_label in batch_labels:
                in_price, out_price = in_price / 2, out_price / 2
            cell_cost = (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price
        cell_cost *= runs_per_cell

        bucket = by_model.setdefault(cell.model_label, {"n_cells": 0, "estimated_usd": 0.0})
        bucket["n_cells"] += 1
        bucket["estimated_usd"] += cell_cost
        total_usd += cell_cost

    return {
        "n_grid_cells": len(cells),
        "runs_per_cell": runs_per_cell,
        "total_calls": len(cells) * runs_per_cell,
        "estimated_total_usd": round(total_usd, 2),
        "by_model": {k: {"n_cells": v["n_cells"], "estimated_usd": round(v["estimated_usd"], 2)} for k, v in by_model.items()},
        "models_missing_pricing_data": sorted(missing_pricing),
        "batch_discounted_labels": sorted(batch_labels),
        "note": (
            "Token counts are a ~4 chars/token heuristic, not a real tokenizer, "
            "and output tokens assume the worst case (max_output_tokens) for "
            "every call. Treat this as an upper-bound-ish estimate, not exact."
            + (
                f" Labels {sorted(batch_labels)} are priced at the ~50%-off batch "
                f"rate, not the synchronous rate - see BATCH_ELIGIBLE_LABELS."
                if batch_labels else ""
            )
        ),
    }


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_run_config(**fields) -> None:
    RUN_CONFIG_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_CONFIG_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(fields) + "\n")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _finalize_run(
    project_id: str,
    model_label: str,
    model_version: str,
    prompt_strategy: str,
    run_index: int,
    temperature: float,
    temperature_applied: bool,
    raw_text: str,
) -> Path:
    """Parse raw_text, write the raw-output record, and log to
    run_config.jsonl - the part of run_one() that is identical regardless of
    HOW raw_text was obtained. Factored out 2026-07-21 so the batch-API path
    (check_and_collect_batches, which gets raw_text back from a provider's
    batch results endpoint, possibly hours after submission) writes records
    in the EXACT same shape as the synchronous path. Every downstream
    consumer (match.py, metrics.py, judge.py, build_rater_packets.py) reads
    results/raw_outputs/*.json and run_config.jsonl without caring which path
    produced them - this function is the single place that shape is defined.
    """
    out_path = raw_output_path(project_id, model_label, prompt_strategy, run_index)
    if out_path.exists():
        raise FileExistsError(
            f"{out_path} already exists - raw outputs are append-only and are "
            f"never overwritten. This should not happen if next_free_run_index "
            f"(sync path) or build_batch_units (batch path) was used to assign "
            f"run_index; if calling this directly, pick an unused run_index."
        )

    parsed, parse_error = parse_model_response(raw_text, prompt_strategy)
    run_date = datetime.now(timezone.utc).isoformat()

    record = {
        "project_id": project_id,
        "model": model_label,
        "model_version": model_version,
        "prompt_strategy": prompt_strategy,
        "run_index": run_index,
        "temperature": temperature,
        # False only when the provider rejected the temperature parameter
        # outright and call_gpt() retried without it (see its docstring) -
        # in that case `temperature` above is the REQUESTED value, not what
        # was actually used. Always True for claude/opensource today. For a
        # batch-sourced GPT record, True here means the batch row succeeded
        # WITH temperature applied as requested - see _check_gpt_batch for
        # what happens to a row that errors on temperature instead (it is
        # recorded as a failure, not silently retried - batch rows cannot be
        # interactively retried the way the synchronous call_gpt() can).
        "temperature_applied": temperature_applied,
        "run_date": run_date,
        "prompt_sha256": prompt_file_sha256(prompt_strategy),
        "raw_response_text": raw_text,
        "parsed_risks": parsed,
        "parse_error": parse_error,
    }
    RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    log_run_config(
        project_id=project_id,
        model=model_label,
        model_version=model_version,
        prompt_strategy=prompt_strategy,
        run_index=run_index,
        run_date=run_date,
        temperature=temperature,
        temperature_applied=temperature_applied,
        prompt_sha256=record["prompt_sha256"],
        raw_output_path=str(out_path.relative_to(REPO_ROOT)),
        parse_failed=parsed is None,
    )
    return out_path


def run_one(project_id: str, model_label: str, prompt_strategy: str, run_index: int, temperature: float, max_tokens: int) -> Path:
    out_path = raw_output_path(project_id, model_label, prompt_strategy, run_index)
    if out_path.exists():
        raise FileExistsError(
            f"{out_path} already exists - raw outputs are append-only and are "
            f"never overwritten. This should not happen if next_free_run_index "
            f"was used; if calling run_one directly, pick an unused run_index."
        )

    model_version = resolve_model_version(model_label)
    prompt = render_prompt(prompt_strategy, project_id)
    raw_text, temperature_applied = _call_model_with_retry(model_label, prompt, model_version, temperature, max_tokens)
    return _finalize_run(
        project_id, model_label, model_version, prompt_strategy, run_index,
        temperature, temperature_applied, raw_text,
    )


# ---------------------------------------------------------------------------
# Batch API support (Anthropic + OpenAI only - see BATCH_ELIGIBLE_LABELS).
#
# Both providers' batch endpoints are asynchronous (results can take up to
# 24h), so this is a two-phase, non-blocking design rather than a drop-in
# replacement for run_one(): `--batch` SUBMITS and exits immediately;
# `--batch-check` (re-runnable any number of times) polls and, for anything
# finished, retrieves and writes results through the same _finalize_run()
# the synchronous path uses. Real SDK method/field names below were
# confirmed 2026-07-21 via inspect.signature() and direct source reads
# against the actually-installed anthropic==0.117.0 / openai==1.109.1 - not
# yet exercised against a live call (no real API key has ever existed for
# this project); verify against BATCH_JOBS_LOG and a real raw_outputs record
# the first time a real submit/check cycle runs, the same way call_gpt's
# temperature-retry path is flagged for first-real-call verification.
# ---------------------------------------------------------------------------

def build_batch_units(cells: list["GridCell"], runs_per_cell: int, label: str) -> list[dict]:
    """Expand the cells matching `label` into one unit dict per individual
    run, assigning run_index via next_free_run_index up front. Fixed at
    submission time so the (project_id, model_label, prompt_strategy,
    run_index) mapping stays correct no matter when results actually arrive -
    unlike the synchronous path, a batch can take up to 24h and results can
    arrive in any order, well after a fresh next_free_run_index() query would
    give a different answer for the same combo."""
    units = []
    for cell in cells:
        if cell.model_label != label:
            continue
        start = next_free_run_index(cell.project_id, cell.model_label, cell.prompt_strategy)
        for i in range(runs_per_cell):
            units.append({
                "project_id": cell.project_id,
                "model_label": cell.model_label,
                "prompt_strategy": cell.prompt_strategy,
                "run_index": start + i,
            })
    return units


def _batch_custom_id(label: str, i: int) -> str:
    """Short and sequential by construction - deliberately NOT encoding
    project_id/prompt_strategy/run_index directly. Some real project_ids in
    this corpus (e.g. 'P-MAR-SecondIdentityTargetingSocialProtection')
    combined with a '__model__prompt__runN' suffix risk exceeding
    Anthropic's custom_id length limit (~64 chars). The real mapping back to
    (project_id, model_label, prompt_strategy, run_index) is carried in
    BATCH_JOBS_LOG's per-job `units` list instead."""
    return f"req-{label}-{i:05d}"


def _load_batch_jobs() -> list[dict]:
    if not BATCH_JOBS_LOG.exists():
        return []
    with open(BATCH_JOBS_LOG, encoding="utf-8") as f:
        return json.load(f)


def _save_batch_jobs(jobs: list[dict]) -> None:
    BATCH_JOBS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(BATCH_JOBS_LOG, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)


def submit_claude_batch(units: list[dict], model_version: str, temperature: float, max_tokens: int) -> str:
    """units: from build_batch_units(..., label='claude'), each already
    carrying a custom_id (set by the caller, submit_batch_grid). Returns the
    Anthropic batch id.

    Request shape confirmed against anthropic.types.messages.batch_create_params:
    Request = {"custom_id": str, "params": <same shape as messages.create()>}.
    """
    import anthropic

    api_key = _require_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    requests = []
    for u in units:
        prompt = render_prompt(u["prompt_strategy"], u["project_id"])
        requests.append({
            "custom_id": u["custom_id"],
            "params": {
                "model": model_version,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
        })
    batch = client.messages.batches.create(requests=requests)
    return batch.id


def submit_gpt_batch(units: list[dict], model_version: str, temperature: float, max_tokens: int) -> str:
    """units: from build_batch_units(..., label='gpt'), each already carrying
    a custom_id. Returns the OpenAI batch id.

    Uses max_completion_tokens (not max_tokens) - same reasoning-model
    finding as the synchronous call_gpt(), see its docstring. UNLIKE
    call_gpt(), there is deliberately NO defensive temperature retry here: a
    batch request the API rejects for the same "reasoning models reject
    temperature" reason fails that one JSONL line (surfaced in
    _check_gpt_batch as an errored row with a diagnostic hint pointing back
    here), not a live retry - batch requests are submit-once, and
    resubmitting a fresh one-line batch per failed row isn't implemented. If
    EVERY gpt row in a real batch comes back errored mentioning temperature,
    that is real evidence the sync-path constraint applies to the batch
    endpoint too and this function needs the same unconditional omission -
    not knowable without a real batch attempt (no OPENAI_API_KEY has ever
    existed for this project).
    """
    import openai

    api_key = _require_env("OPENAI_API_KEY")
    client = openai.OpenAI(api_key=api_key)
    lines = []
    for u in units:
        prompt = render_prompt(u["prompt_strategy"], u["project_id"])
        lines.append(json.dumps({
            "custom_id": u["custom_id"],
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model_version,
                "max_completion_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
        }))
    jsonl_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    uploaded = client.files.create(file=("batch_input.jsonl", jsonl_bytes), purpose="batch")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    return batch.id


def submit_batch_grid(cells: list["GridCell"], runs_per_cell: int, temperature: float, max_tokens: int) -> dict:
    """Submits one Anthropic batch (if any claude cells) and/or one OpenAI
    batch (if any gpt cells) covering every requested run for those two
    providers only - see BATCH_ELIGIBLE_LABELS. Does NOT touch opensource
    cells; the caller (main()) still runs those synchronously via the normal
    run_one() loop, same as always.

    Appends one job entry per submitted batch to BATCH_JOBS_LOG, each
    carrying its own `units` list so check_and_collect_batches() can map
    results back to (project_id, model_label, prompt_strategy, run_index)
    without recomputing anything. Does NOT wait for anything to finish -
    batch jobs can take up to 24h; call check_and_collect_batches()
    (--batch-check) later, any number of times, to poll and collect.
    """
    jobs = _load_batch_jobs()
    submitted = []

    for label in sorted(BATCH_ELIGIBLE_LABELS):
        units = build_batch_units(cells, runs_per_cell, label)
        if not units:
            continue
        model_version = resolve_model_version(label)
        for i, u in enumerate(units):
            u["custom_id"] = _batch_custom_id(label, i)

        if label == "claude":
            batch_id = submit_claude_batch(units, model_version, temperature, max_tokens)
            provider = "anthropic"
        elif label == "gpt":
            batch_id = submit_gpt_batch(units, model_version, temperature, max_tokens)
            provider = "openai"
        else:
            raise AssertionError(f"BATCH_ELIGIBLE_LABELS contains unhandled label {label!r}")

        job = {
            "batch_id": batch_id,
            "provider": provider,
            "model_label": label,
            "model_version": model_version,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "submitted",
            "units": units,
        }
        jobs.append(job)
        submitted.append({"provider": provider, "model_label": label, "batch_id": batch_id, "n_requests": len(units)})
        # Persist after EVERY successful submission, not once at the end of the
        # loop. claude and gpt are submitted to two different providers in
        # sequence (sorted(BATCH_ELIGIBLE_LABELS) = ["claude", "gpt"]); if the
        # claude batch is accepted (money spent, job now running at Anthropic)
        # and the gpt submission then raises (missing OPENAI_API_KEY, a
        # transient network error, anything), a save-once-at-the-end design
        # would lose the claude batch_id entirely - BATCH_JOBS_LOG would have
        # no record of it, so --batch-check could never find or collect a job
        # that is actually running and will actually be billed. Saving here
        # means a partial failure still leaves every already-submitted batch
        # recorded and collectible.
        _save_batch_jobs(jobs)

    return {
        "submitted": submitted,
        "batch_jobs_log": str(BATCH_JOBS_LOG.relative_to(REPO_ROOT)),
        "note": (
            "Submitted, not completed. Batch jobs can take up to 24h (Anthropic "
            "often finishes faster; OpenAI's completion_window is fixed at 24h). "
            "Run `python src/run_experiments.py --batch-check` later - any "
            "number of times - to poll and collect finished results; "
            "already-collected jobs are skipped on repeat calls."
        ),
    }


def _check_claude_batch(batch_id: str) -> tuple[str, list[tuple[str, Optional[str], bool]]]:
    """Returns (processing_status, results). results is only populated once
    processing_status == 'ended'; each item is
    (custom_id, response_text_or_None, ok)."""
    import anthropic

    api_key = _require_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    batch = client.messages.batches.retrieve(batch_id)
    if batch.processing_status != "ended":
        return batch.processing_status, []

    results = []
    for item in client.messages.batches.results(batch_id):
        if item.result.type == "succeeded":
            text = "".join(
                block.text for block in item.result.message.content
                if getattr(block, "type", None) == "text"
            )
            results.append((item.custom_id, text, True))
        else:
            detail = getattr(item.result, "error", None)
            print(
                f"[batch] claude {item.custom_id}: {item.result.type}"
                + (f" - {detail}" if detail is not None else ""),
                file=sys.stderr,
            )
            results.append((item.custom_id, None, False))
    return "ended", results


def _check_gpt_batch(batch_id: str) -> tuple[str, list[tuple[str, Optional[str], bool]]]:
    """Returns (status, results), same shape as _check_claude_batch. results
    is only populated once status == 'completed'."""
    import openai

    api_key = _require_env("OPENAI_API_KEY")
    client = openai.OpenAI(api_key=api_key)
    batch = client.batches.retrieve(batch_id)
    if batch.status != "completed":
        return batch.status, []

    results = []
    if batch.output_file_id:
        content = client.files.content(batch.output_file_id).text
        for line in content.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            custom_id = row["custom_id"]
            resp = row.get("response")
            if resp and resp.get("status_code") == 200:
                text = resp["body"]["choices"][0]["message"]["content"] or ""
                results.append((custom_id, text, True))
            else:
                err = row.get("error") or (resp or {}).get("body", {}).get("error")
                hint = ""
                if err and "temperature" in json.dumps(err).lower():
                    hint = (" (mentions temperature - may be the same reasoning-model "
                            "rejection call_gpt() handles in the sync path; see "
                            "submit_gpt_batch's docstring)")
                print(f"[batch] gpt {custom_id}: FAILED - {err}{hint}", file=sys.stderr)
                results.append((custom_id, None, False))
    if batch.error_file_id:
        # Rows OpenAI rejected before attempting (malformed request, etc.) -
        # surfaced for visibility. Not folded into `results` above since a
        # clean custom_id -> reason mapping from this file isn't guaranteed;
        # inspecting it directly is the reliable path if this ever fires.
        print(
            f"[batch] gpt batch {batch_id} has an error_file_id "
            f"({batch.error_file_id}) - some requests were rejected before "
            f"processing. Inspect via client.files.content({batch.error_file_id!r}) "
            f"or the OpenAI dashboard.",
            file=sys.stderr,
        )
    return "completed", results


def check_and_collect_batches() -> dict:
    """Reads BATCH_JOBS_LOG, checks every not-yet-collected job's status, and
    for any that finished, retrieves results and writes them through
    _finalize_run - the exact same record shape run_one() produces, so
    match.py/metrics.py/judge.py/build_rater_packets.py need no changes and
    cannot tell a batch-sourced run from a synchronous one. Safe to call any
    number of times: already-collected jobs are skipped, and a row already
    written by an earlier partial collection is treated as done (not a new
    failure) via the same FileExistsError catch _finalize_run always raises
    on a re-write attempt."""
    jobs = _load_batch_jobs()
    if not jobs:
        return {
            "jobs": [],
            "note": f"{BATCH_JOBS_LOG.relative_to(REPO_ROOT)} has no recorded jobs - "
                    f"nothing to check. Submit with --batch first.",
        }

    report = []
    for job in jobs:
        if job["status"] == "collected":
            report.append({"batch_id": job["batch_id"], "provider": job["provider"], "status": "already collected"})
            continue

        if job["provider"] == "anthropic":
            status, results = _check_claude_batch(job["batch_id"])
        elif job["provider"] == "openai":
            status, results = _check_gpt_batch(job["batch_id"])
        else:
            raise AssertionError(f"unknown provider {job['provider']!r} in {BATCH_JOBS_LOG}")

        if status not in ("ended", "completed"):
            report.append({"batch_id": job["batch_id"], "provider": job["provider"], "status": status})
            continue

        units_by_custom_id = {u["custom_id"]: u for u in job["units"]}
        n_ok, n_failed, n_already_written = 0, 0, 0
        for custom_id, text, ok in results:
            u = units_by_custom_id.get(custom_id)
            if u is None:
                print(f"[batch] WARNING: {job['provider']} batch {job['batch_id']} returned "
                      f"unrecognized custom_id {custom_id!r} - skipped", file=sys.stderr)
                continue
            if not ok:
                n_failed += 1
                continue
            try:
                _finalize_run(
                    u["project_id"], u["model_label"], job["model_version"], u["prompt_strategy"],
                    u["run_index"], job["temperature"], True, text,
                )
                n_ok += 1
            except FileExistsError:
                n_already_written += 1

        job["status"] = "collected"
        job["collected_at"] = datetime.now(timezone.utc).isoformat()
        report.append({
            "batch_id": job["batch_id"], "provider": job["provider"], "status": "collected",
            "n_ok": n_ok, "n_failed": n_failed, "n_already_written": n_already_written,
        })

    _save_batch_jobs(jobs)
    return {"jobs": report}


def all_project_ids() -> list[str]:
    """Default project list for the experimental grid: every 'included' row in
    corpus_manifest.csv (NOT simply every file in data/processed/ - that
    directory also contains the set-aside outlier, P-REGION-AIM4Learning,
    which extract.py processes like any other row but which is explicitly
    excluded from the evaluation corpus per its manifest note. Defaulting to
    a raw directory glob here would silently pull it back into the grid)."""
    import csv

    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        included = [row["project_id"] for row in csv.DictReader(f) if row["inclusion_status"] == "included"]
    available = {p.stem for p in PROCESSED_DIR.glob("*.txt")}
    missing = [pid for pid in included if pid not in available]
    if missing:
        raise FileNotFoundError(
            f"corpus_manifest.csv marks these as 'included' but data/processed/ "
            f"has no matching file: {missing}. Run extract.py --all first."
        )
    return sorted(included)


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", action="append", help="Project id (repeatable). Default: all in data/processed/")
    parser.add_argument("--model", action="append", choices=list(MODEL_DISPATCH), help="Model label (repeatable). Default: all three")
    parser.add_argument("--prompt", action="append", choices=list(PROMPT_FILES), help="Prompt strategy (repeatable). Default: all three")
    parser.add_argument("--runs", type=int, default=1, help="Runs per (project, model, prompt) combination")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--estimate-only", action="store_true", help="Print the cost estimate and exit without calling any API")
    parser.add_argument("--confirm-cost", action="store_true", help=f"Required to proceed if the estimate exceeds ${COST_GUARD_THRESHOLD_USD:.0f}")
    parser.add_argument(
        "--batch", action="store_true",
        help=(
            f"Submit claude+gpt cells as batch jobs (~50%% off list price) instead of "
            f"calling synchronously; opensource cells still run synchronously (see "
            f"BATCH_ELIGIBLE_LABELS). Submits and exits immediately without waiting - "
            f"batch jobs can take up to 24h. Use --batch-check afterward to collect "
            f"results. The cost estimate/guard below reflects the batch discount when "
            f"this flag is set. Mutually exclusive with --batch-check."
        ),
    )
    parser.add_argument(
        "--batch-check", action="store_true",
        help=(
            f"Poll every pending job in results/batch_jobs.json and collect any that "
            f"finished, writing results through the same code path a synchronous run "
            f"uses. Ignores --project/--model/--prompt/--runs/--temperature/--max-tokens "
            f"entirely (each job already recorded what it needs). Safe to re-run any "
            f"number of times."
        ),
    )
    args = parser.parse_args()

    if args.batch and args.batch_check:
        parser.error("--batch and --batch-check are mutually exclusive: submit with --batch, then check separately with --batch-check.")

    if args.batch_check:
        report = check_and_collect_batches()
        print(json.dumps(report, indent=2))
        return

    if not (0.0 <= args.temperature <= 0.2):
        parser.error(f"--temperature must be in [0, 0.2] per CLAUDE.md; got {args.temperature}")

    assert_no_ground_truth_leakage()

    project_ids = args.project or all_project_ids()
    models = args.model or list(MODEL_DISPATCH)
    prompts = args.prompt or list(PROMPT_FILES)

    cells = [
        GridCell(project_id=p, model_label=m, prompt_strategy=pr)
        for p in project_ids
        for m in models
        for pr in prompts
    ]

    # Cost estimate must reflect what will ACTUALLY be spent: batch-eligible
    # labels at the discounted rate when --batch is set, so the guard isn't
    # comparing --confirm-cost against a synchronous price nobody is paying.
    batch_labels = BATCH_ELIGIBLE_LABELS if args.batch else frozenset()
    estimate = estimate_cost(cells, args.runs, args.max_tokens, batch_labels=batch_labels)
    print(json.dumps(estimate, indent=2))

    if estimate["models_missing_pricing_data"]:
        print(
            f"\nWARNING: no pricing data for: {estimate['models_missing_pricing_data']}. "
            f"Cost estimate above EXCLUDES these - it is understated, not zero. "
            f"Add them to PRICING_PER_MTOK before trusting this estimate.",
            file=sys.stderr,
        )

    if args.estimate_only:
        return

    if estimate["estimated_total_usd"] > COST_GUARD_THRESHOLD_USD and not args.confirm_cost:
        print(
            f"\nCOST GUARD: estimated ${estimate['estimated_total_usd']:.2f} exceeds "
            f"the ${COST_GUARD_THRESHOLD_USD:.0f} threshold (CLAUDE.md). Re-run with "
            f"--confirm-cost to proceed, after checking the estimate above is sane.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.batch:
        batch_cells = [c for c in cells if c.model_label in BATCH_ELIGIBLE_LABELS]
        sync_cells = [c for c in cells if c.model_label not in BATCH_ELIGIBLE_LABELS]

        if batch_cells:
            submission = submit_batch_grid(batch_cells, args.runs, args.temperature, args.max_tokens)
            print(json.dumps(submission, indent=2))
            for s in submission["submitted"]:
                print(f"[batch] submitted {s['provider']} batch {s['batch_id']} "
                      f"({s['n_requests']} requests, model={s['model_label']})")
        else:
            print("[batch] no claude/gpt cells in this selection - nothing to submit as a batch.", file=sys.stderr)

        if not sync_cells:
            print("[batch] no opensource cells in this selection - nothing left to run "
                  "synchronously. Use --batch-check later to collect the submitted batch(es).")
            return

        # Non-batch-eligible cells (opensource today) still run synchronously,
        # exactly like the non-batch path, just restricted to this subset.
        cells = sync_cells

    n_failed = 0
    n_ok = 0
    for cell in cells:
        for _ in range(args.runs):
            run_index = next_free_run_index(cell.project_id, cell.model_label, cell.prompt_strategy)
            try:
                out_path = run_one(cell.project_id, cell.model_label, cell.prompt_strategy, run_index, args.temperature, args.max_tokens)
                print(f"[run] {cell.project_id} / {cell.model_label} / {cell.prompt_strategy} run{run_index} -> {out_path.relative_to(REPO_ROOT)}")
                n_ok += 1
            except Exception as e:
                print(f"[run] FAILED {cell.project_id} / {cell.model_label} / {cell.prompt_strategy} run{run_index}: {e}", file=sys.stderr)
                n_failed += 1

    print(f"\n[run_experiments] {n_ok} succeeded, {n_failed} failed.", file=sys.stderr)
    if n_failed and not n_ok:
        # Every single call failed - almost certainly a systemic problem (bad
        # keys, no network, etc.), not per-call noise. Exit non-zero so this
        # is never silently mistaken for a completed run by calling scripts.
        sys.exit(2)
    elif n_failed:
        sys.exit(3)


if __name__ == "__main__":
    main()
