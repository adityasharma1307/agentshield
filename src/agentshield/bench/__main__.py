"""`python -m agentshield.bench live|local|render`."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from agentshield.audit import collect_breaches, load_agent
from agentshield.bench.render import render_document
from agentshield.scenarios.loader import load_scenarios, shipped_suites_dir
from agentshield.scoring.policy import load_policy

_PROVIDER_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
}


def main(argv: list[str] | None = None) -> int:
    """Run a bench subcommand. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="python -m agentshield.bench")
    sub = parser.add_subparsers(dest="command", required=True)
    live = sub.add_parser(
        "live",
        help="Score a model list. Exits 2 when a provider key is missing.",
    )
    live.add_argument("models", type=Path, help="Text file with one LiteLLM model id per line.")
    live.add_argument("--suite", type=Path, default=None)
    live.add_argument("--policy", type=Path, default=None)
    live.add_argument("--out", type=Path, default=None)
    local = sub.add_parser("local", help="Score the example agents. Does not call a provider.")
    local.add_argument("--suite", type=Path, default=None)
    local.add_argument("--policy", type=Path, default=None)
    local.add_argument("--out", type=Path, required=True)
    render = sub.add_parser("render", help="Write RESULTS markdown from a results JSON file.")
    render.add_argument("results", type=Path)
    render.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "live":
        return _live(args.models, args.suite, args.policy, args.out)
    if args.command == "local":
        return _local(args.suite, args.policy, args.out)
    if args.command == "render":
        payload = json.loads(args.results.read_text(encoding="utf-8"))
        args.out.write_text(render_document(payload), encoding="utf-8")
        return 0
    parser.print_help()
    return 2


def provider_env(model: str) -> str | None:
    """The environment variable LiteLLM needs for `model`, or None when it is unknown."""
    prefix = model.split("/", 1)[0]
    return _PROVIDER_KEYS.get(prefix)


def missing_provider_keys(models: list[str]) -> list[str]:
    """Provider variables that are unset. Unknown providers are reported by name."""
    missing: list[str] = []
    for model in models:
        variable = provider_env(model)
        if variable is None:
            missing.append(f"unsupported model provider in {model}")
            continue
        if not os.environ.get(variable):
            missing.append(variable)
    return list(dict.fromkeys(missing))


def read_model_list(path: Path) -> list[str]:
    """Non-empty, non-comment lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def rows_for_agent(model: str, directory: Path, policy_path: Path) -> list[dict[str, Any]]:
    """One row per suite from a real run. A scenario fails when any gate rule fails."""
    entry = model if ":" in model else f"{model}.agent:agent"
    agent = load_agent(entry)
    policy = load_policy(policy_path)
    breaches = asyncio.run(collect_breaches(directory, agent, policy, fail_on="high"))
    failed_ids = {breach.scenario_id for breach in breaches}
    return suite_rows(model, directory, failed_ids)


def suite_rows(model: str, directory: Path, failed_ids: set[str]) -> list[dict[str, Any]]:
    """Count passed and failed scenarios in each suite."""
    grouped: dict[str, list[str]] = {}
    for scenario in load_scenarios(directory):
        grouped.setdefault(scenario.suite, []).append(scenario.id)
    rows: list[dict[str, Any]] = []
    for suite in sorted(grouped):
        ids = grouped[suite]
        failed = sum(1 for scenario_id in ids if scenario_id in failed_ids)
        rows.append(
            {
                "model": model,
                "suite": suite,
                "scenarios": len(ids),
                "passed": len(ids) - failed,
                "failed": failed,
            }
        )
    return rows


def _live(models_path: Path, suite: Path | None, policy: Path | None, out: Path | None) -> int:
    if not models_path.is_file():
        print(f"model list not found: {models_path}", file=sys.stderr)
        return 2
    models = read_model_list(models_path)
    if not models:
        print("model list is empty", file=sys.stderr)
        return 2
    missing = missing_provider_keys(models)
    if missing:
        for name in missing:
            print(f"missing environment variable: {name}", file=sys.stderr)
        return 2
    destination = out or Path("results") / f"{date.today().isoformat()}.json"
    try:
        payload = _live_payload(models, suite, policy)
    except ImportError:
        print("live benchmarks require the agentshield[bench] extra", file=sys.stderr)
        return 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(destination)
    return 0


def _live_payload(models: list[str], suite: Path | None, policy: Path | None) -> dict[str, Any]:
    """Call LiteLLM. Only reached when every listed provider key is set."""
    import litellm

    directory = shipped_suites_dir() if suite is None else suite
    policy_path = _policy(policy)
    rows: list[dict[str, Any]] = []
    for model in models:
        rows.extend(_rows_for_litellm(model, directory, policy_path, litellm))
    return {"note": "Live LiteLLM runs.", "rows": rows}


def _rows_for_litellm(
    model: str,
    directory: Path,
    policy_path: Path,
    litellm: Any,
) -> list[dict[str, Any]]:
    from agentshield.adapters.openai_sdk import OpenAISdkAgent

    class _Completions:
        async def create(self, **kwargs: Any) -> Any:
            return await litellm.acompletion(**kwargs)

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    agent = OpenAISdkAgent(model=model, client=_Client())
    policy = load_policy(policy_path)
    breaches = asyncio.run(collect_breaches(directory, agent, policy, fail_on="high"))
    failed_ids = {breach.scenario_id for breach in breaches}
    return suite_rows(model, directory, failed_ids)


def _local(suite: Path | None, policy: Path | None, out: Path) -> int:
    directory = shipped_suites_dir() if suite is None else suite
    policy_path = _policy(policy)
    agents = [
        "examples.careful_agent",
        "examples.leaky_agent",
    ]
    rows: list[dict[str, Any]] = []
    for agent in agents:
        rows.extend(rows_for_agent(agent, directory, policy_path))
    payload = {
        "note": (
            "Local runs of the example agents against the shipped suites. "
            "Not a live model benchmark."
        ),
        "rows": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0


def _policy(path: Path | None) -> Path:
    from agentshield.audit import default_policy_path

    return default_policy_path() if path is None else path


if __name__ == "__main__":
    raise SystemExit(main())
