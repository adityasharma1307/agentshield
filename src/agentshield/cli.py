"""Command-line entrypoint for Agentshield."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from agentshield import __version__
from agentshield.audit import (
    collect_breaches,
    default_policy_path,
    load_agent,
    summary_markdown,
    write_step_summary,
)
from agentshield.report.schema import SignedReport, canonical_bytes
from agentshield.report.signing import ML_DSA_ALG, QKNOT_ALG, LocalSigner, qknot_verify, verify
from agentshield.scenarios.dsl import ScenarioLoadError
from agentshield.scenarios.loader import load_scenarios, shipped_suites_dir
from agentshield.scoring.policy import PolicyLoadError, load_policy


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="agentshield",
        description="Compliance and red-teaming harness for tool-using LLM agents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    scenarios = subparsers.add_parser(
        "scenarios",
        help="List scenario id, suite, and expectation names. Does not run them.",
    )
    scenarios.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directory of scenario YAML files. Defaults to the shipped suites.",
    )
    verify_cmd = subparsers.add_parser(
        "verify",
        help="Check a signed report. Exit 0 on a match, 1 on a mismatch, 2 on usage errors.",
    )
    verify_cmd.add_argument("report", type=Path, help="Path to a signed report JSON file.")
    verify_cmd.add_argument(
        "--key",
        type=Path,
        default=None,
        help=(
            "Signer secret for algorithm local, or the ML-DSA public key for "
            "ML-DSA-44. qknot bundles carry their own public keys."
        ),
    )
    run_cmd = subparsers.add_parser(
        "run",
        help="Run a suite, score it, and exit 1 when a rule at or above --fail-on fails.",
    )
    run_cmd.add_argument("--agent", required=True, help="Agent entry, module:attribute.")
    run_cmd.add_argument(
        "--suite",
        type=Path,
        default=None,
        help="Directory of scenario YAML files. Defaults to the shipped suites.",
    )
    run_cmd.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Policy YAML file. Defaults to the shipped policy.",
    )
    run_cmd.add_argument(
        "--fail-on",
        default="high",
        choices=["low", "medium", "high", "critical"],
        help="Lowest severity that fails the process. Default: high.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scenarios":
        directory = args.dir if isinstance(args.dir, Path) else None
        return _list_scenarios(directory)
    if args.command == "run":
        suite = args.suite if isinstance(args.suite, Path) else None
        policy = args.policy if isinstance(args.policy, Path) else None
        agent = args.agent if isinstance(args.agent, str) else ""
        fail_on = args.fail_on if isinstance(args.fail_on, str) else "high"
        return _run_suite(agent, suite, policy, fail_on)
    if args.command == "verify":
        report = args.report if isinstance(args.report, Path) else None
        key = args.key if isinstance(args.key, Path) else None
        if report is None:
            print("report path is required", file=sys.stderr)
            return 2
        return _verify_report(report, key)
    parser.print_help()
    return 0


def _run_suite(agent_entry: str, suite: Path | None, policy_path: Path | None, fail_on: str) -> int:
    suite = shipped_suites_dir() if suite is None else suite
    policy_file = default_policy_path() if policy_path is None else policy_path
    try:
        agent = load_agent(agent_entry)
        policy = load_policy(policy_file)
        breaches = asyncio.run(collect_breaches(suite, agent, policy, fail_on=fail_on))
    except (ScenarioLoadError, PolicyLoadError, ValueError, TypeError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_step_summary(summary_markdown(breaches, fail_on=fail_on))
    return 1 if breaches else 0


def _list_scenarios(directory: Path | None) -> int:
    directory = shipped_suites_dir() if directory is None else directory
    try:
        scenarios = load_scenarios(directory)
    except ScenarioLoadError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for scenario in scenarios:
        names = ",".join(scenario.expect.names())
        print(f"{scenario.id}\t{scenario.suite}\t{names}")
    return 0


def _verify_report(path: Path, key_path: Path | None) -> int:
    if not path.is_file():
        print(f"report not found: {path}", file=sys.stderr)
        return 2
    try:
        signed = SignedReport.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"report is not a signed report: {exc}", file=sys.stderr)
        return 2
    needs_key = signed.algorithm != QKNOT_ALG
    if needs_key and (key_path is None or not key_path.is_file()):
        print("verify requires --key pointing at the signer key", file=sys.stderr)
        return 2
    payload = canonical_bytes(signed.report)
    key = b"" if key_path is None or not key_path.is_file() else key_path.read_bytes()
    try:
        matches = _signature_matches(signed.algorithm, payload, signed.signature, key)
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("signature matches" if matches else "signature does not match")
    return 0 if matches else 1


def _signature_matches(algorithm: str, payload: bytes, signature: str, key: bytes) -> bool:
    if algorithm == "local":
        return LocalSigner(key).verify(payload, signature)
    if algorithm == ML_DSA_ALG:
        return verify(payload, signature, key)
    if algorithm == QKNOT_ALG:
        return qknot_verify(payload, signature)
    raise ValueError(f"unknown signature algorithm {algorithm!r}")


if __name__ == "__main__":
    raise SystemExit(main())
