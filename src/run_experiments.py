"""run_experiments.py - drive the 3 models x 3 prompts x ~20 projects grid.

IMPLEMENTED 2026-07-19 with explicit user approval, after the project's own
10-document ground-truth validation gate was crossed (18/18 non-set-aside
documents). NOTE: this file is code-complete but CANNOT be run for a real
experiment yet - .env has no API keys configured as of this writing, and the
exact model tier for each of the 3 models ("Claude", "GPT", "one open-source
model") is still an open research-design decision, deliberately NOT picked
here (see CLAUDE.md: "Never expand scope ... without asking first" - which
model tier to benchmark is a scope decision, not an engineering one). Set
CLAUDE_MODEL_NAME / GPT_MODEL_NAME / OPENSOURCE_MODEL_NAME in .env before
running; the script raises a clear error rather than silently defaulting if
any of these are unset at run time.

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

PROMPT_FILES = {
    "zero_shot": PROMPTS_DIR / "zero_shot.txt",
    "few_shot": PROMPTS_DIR / "few_shot.txt",
    "structured": PROMPTS_DIR / "structured.txt",
}

DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.1  # within CLAUDE.md's required 0-0.2 range
COST_GUARD_THRESHOLD_USD = 30.0

# --- Pricing, USD per million tokens (input, output). See module docstring
# for sourcing/confidence notes. Keyed by the exact model ID string so the
# script can price whichever specific model the .env config points at.
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic - fetched directly from platform.claude.com/docs, 2026-07-19.
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),  # introductory rate through 2026-08-31
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    # OpenAI - web-search summary only, 2026-07-19, re-verify before trusting.
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


def call_claude(prompt: str, model_version: str, temperature: float, max_tokens: int) -> tuple[str, bool]:
    """Returns (response_text, temperature_applied). Anthropic's Messages API
    has no known reasoning-mode restriction on temperature, so this always
    returns True - see call_gpt for why that second value isn't always True
    for every provider."""
    import anthropic

    api_key = _require_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model_version,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    return text, True


def call_gpt(prompt: str, model_version: str, temperature: float, max_tokens: int) -> tuple[str, bool]:
    """Returns (response_text, temperature_applied).

    FINDING sourced 2026-07-20 (web search, not yet exercised against a real
    call - no OPENAI_API_KEY has existed at any point this was written; verify
    on the first real run): OpenAI's GPT-5-family "reasoning" models -
    plausibly including gpt-5.6-terra, the model this project has selected -
    are documented to (a) reject the legacy `max_tokens` parameter on
    chat.completions.create() in favor of `max_completion_tokens` (this is
    now the OpenAI-recommended parameter broadly, not model-specific, so it's
    switched below unconditionally), and (b) reject `temperature` outright
    when reasoning_effort != "none" (see developers.openai.com/api/docs/guides/
    reasoning#reasoning-mode per the search result that surfaced this).

    (b) directly conflicts with CLAUDE.md's "temperature 0-0.2 across all 3
    models" requirement, which was written before this constraint was known.
    Handled defensively, not silently: try the call with temperature as
    requested; if the API specifically rejects it, retry without temperature
    (the only sane recovery - there is no other way to get a response at
    all), print a loud stderr warning, and return temperature_applied=False
    so run_one() can record - not hide - that this call's actual sampling
    temperature was the model's own default, not the requested value. See the
    paper draft's Limitations section (V.A) for the disclosed methodological
    consequence if this fires on real runs.

    NOT YET CONFIRMED: whether reasoning_effort="none" would restore full
    parameter support instead (which might be preferable to silently losing
    temperature control) - that's a real option to revisit if this retry path
    actually fires on a live call, not assumed here.
    """
    import openai

    api_key = _require_env("OPENAI_API_KEY")
    client = openai.OpenAI(api_key=api_key)
    base_kwargs = dict(
        model=model_version,
        max_completion_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    temperature_applied = True
    try:
        resp = client.chat.completions.create(temperature=temperature, **base_kwargs)
    except openai.BadRequestError as e:
        msg = str(e).lower()
        if "temperature" in msg and ("unsupported" in msg or "not supported" in msg or "does not support" in msg):
            print(
                f"[call_gpt] WARNING: {model_version} rejected temperature={temperature} "
                f"(reasoning-model constraint - see call_gpt's docstring in run_experiments.py). "
                f"Retrying WITHOUT temperature. This call's actual sampling temperature is "
                f"the model's own default, NOT {temperature} - recorded as "
                f"temperature_applied=False in the raw output record and run_config.jsonl.",
                file=sys.stderr,
            )
            resp = client.chat.completions.create(**base_kwargs)
            temperature_applied = False
        else:
            raise
    return resp.choices[0].message.content or "", temperature_applied


def call_opensource(prompt: str, model_version: str, temperature: float, max_tokens: int) -> tuple[str, bool]:
    """Returns (response_text, temperature_applied). Supports either
    documented access path from .env.example: HF hosted inference (HF_TOKEN)
    or a self-hosted/third-party OpenAI-compatible endpoint (OPENSOURCE_BASE_URL
    + OPENSOURCE_API_KEY). Neither is assumed; whichever is configured in .env
    is used, and it is an error if neither is.

    Deliberately still uses classic `max_tokens` (NOT max_completion_tokens,
    contrast with call_gpt above): third-party "OpenAI-compatible" inference
    providers (Together AI, Fireworks, Groq, DeepInfra - see
    docs/model_tier_recommendation.md) serve open-weight models (DeepSeek,
    Llama, Qwen, etc.) that are not OpenAI's own o-series/GPT-5 reasoning
    models and are not known to share this constraint; their compatibility
    layers may not even recognize max_completion_tokens yet. Switching this
    without evidence of an actual problem here would risk breaking a path
    that currently works, for a family of models this restriction wasn't
    sourced against. Revisit if a real run against the chosen provider proves
    otherwise.
    """
    base_url = os.environ.get("OPENSOURCE_BASE_URL")
    opensource_key = os.environ.get("OPENSOURCE_API_KEY")
    hf_token = os.environ.get("HF_TOKEN")

    if base_url:
        import openai

        client = openai.OpenAI(api_key=opensource_key or "unused", base_url=base_url)
        resp = client.chat.completions.create(
            model=model_version,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or "", True
    elif hf_token:
        # Hosted-inference path via huggingface_hub. Deferred import: this
        # dependency is not in requirements.txt yet because the open-source
        # access path has not been decided - add `huggingface_hub` to
        # requirements.txt if this path is the one actually chosen.
        from huggingface_hub import InferenceClient

        client = InferenceClient(model=model_version, token=hf_token)
        text = client.text_generation(prompt, max_new_tokens=max_tokens, temperature=max(temperature, 0.01))
        return text, True
    else:
        raise RuntimeError(
            "Neither OPENSOURCE_BASE_URL nor HF_TOKEN is set in .env - the "
            "open-source model access path has not been configured. This is "
            "a decision for the project owners, not a default this script "
            "should pick silently (see module docstring)."
        )


MODEL_DISPATCH = {
    "claude": call_claude,
    "gpt": call_gpt,
    "opensource": call_opensource,
}


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


def next_free_run_index(project_id: str, model_label: str, prompt_strategy: str) -> int:
    """Append-only: never overwrite an existing run's file. Finds the lowest
    run_index >= 1 with no existing file, so repeated invocations accumulate
    runs rather than clobbering prior ones."""
    idx = 1
    while raw_output_path(project_id, model_label, prompt_strategy, idx).exists():
        idx += 1
    return idx


@dataclass
class GridCell:
    project_id: str
    model_label: str
    prompt_strategy: str


def estimate_cost(cells: list[GridCell], runs_per_cell: int, max_output_tokens: int) -> dict:
    """Estimate total cost across the requested grid before any API calls are
    made. See module docstring for the token-estimation and pricing caveats."""
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
        "note": (
            "Token counts are a ~4 chars/token heuristic, not a real tokenizer, "
            "and output tokens assume the worst case (max_output_tokens) for "
            "every call. Treat this as an upper-bound-ish estimate, not exact."
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
    run_date = datetime.now(timezone.utc).isoformat()

    raw_text, temperature_applied = MODEL_DISPATCH[model_label](prompt, model_version, temperature, max_tokens)
    parsed, parse_error = parse_model_response(raw_text, prompt_strategy)

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
        # was actually used. Always True for claude/opensource today.
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", action="append", help="Project id (repeatable). Default: all in data/processed/")
    parser.add_argument("--model", action="append", choices=list(MODEL_DISPATCH), help="Model label (repeatable). Default: all three")
    parser.add_argument("--prompt", action="append", choices=list(PROMPT_FILES), help="Prompt strategy (repeatable). Default: all three")
    parser.add_argument("--runs", type=int, default=1, help="Runs per (project, model, prompt) combination")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--estimate-only", action="store_true", help="Print the cost estimate and exit without calling any API")
    parser.add_argument("--confirm-cost", action="store_true", help=f"Required to proceed if the estimate exceeds ${COST_GUARD_THRESHOLD_USD:.0f}")
    args = parser.parse_args()

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

    estimate = estimate_cost(cells, args.runs, args.max_tokens)
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
