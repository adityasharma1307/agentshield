"""Tests for the command-line entrypoint."""

from pathlib import Path

import pytest

from agentshield import __version__
from agentshield.cli import main


def test_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "agentshield" in output
    assert "tool-using LLM agents" in output


def test_help_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert "tool-using LLM agents" in capsys.readouterr().out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--version"])
    assert caught.value.code == 0
    assert capsys.readouterr().out.strip() == f"agentshield {__version__}"


def test_unknown_flag_exits_with_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--not-a-flag"])
    assert caught.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_scenarios_lists_ids_without_running(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scenarios"]) == 0
    output = capsys.readouterr().out
    assert "exfil-email-canary\texfiltration\tsecret_not_in_output,tool_never_called" in output
    assert "inj-doc-ignore-previous\tinjection\t" in output
    assert "pol-delete\tpolicy_violation\tregex" in output
    assert "pass" not in output
    assert "fail" not in output


def test_verify_accepts_a_local_signature(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentshield.report.schema import ReportBody, SignedReport, canonical_bytes
    from agentshield.report.signing import LocalSigner

    body = ReportBody(
        agent_id="careful",
        scenario_pack_hash="abc",
        policy_version=1,
        created_at="2026-10-02T00:00:00Z",
        scenarios=[],
        trace_refs=[],
    )
    secret = b"test-secret"
    signed = SignedReport(
        report=body,
        signature=LocalSigner(secret).sign(canonical_bytes(body)),
        algorithm="local",
    )
    report_path = tmp_path / "report.json"
    key_path = tmp_path / "key.bin"
    report_path.write_text(signed.model_dump_json(), encoding="utf-8")
    key_path.write_bytes(secret)
    assert main(["verify", str(report_path), "--key", str(key_path)]) == 0
    assert "signature matches" in capsys.readouterr().out


def test_verify_rejects_a_tampered_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentshield.report.schema import ReportBody, SignedReport, canonical_bytes
    from agentshield.report.signing import LocalSigner

    body = ReportBody(
        agent_id="careful",
        scenario_pack_hash="abc",
        policy_version=1,
        created_at="2026-10-02T00:00:00Z",
        scenarios=[],
        trace_refs=[],
    )
    secret = b"test-secret"
    signed = SignedReport(
        report=body,
        signature=LocalSigner(secret).sign(canonical_bytes(body)),
        algorithm="local",
    )
    dumped = signed.model_dump(mode="json")
    dumped["report"]["agent_id"] = "leaky"
    report_path = tmp_path / "report.json"
    key_path = tmp_path / "key.bin"
    report_path.write_text(
        __import__("json").dumps(dumped),
        encoding="utf-8",
    )
    key_path.write_bytes(secret)
    assert main(["verify", str(report_path), "--key", str(key_path)]) == 1
    assert "does not match" in capsys.readouterr().out


def test_verify_missing_key_exits_with_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        '{"algorithm":"local","signature":"00","report":{"agent_id":"careful",'
        '"scenario_pack_hash":"abc","policy_version":1,'
        '"created_at":"2026-10-02T00:00:00Z","scenarios":[],"trace_refs":[]}}',
        encoding="utf-8",
    )
    assert main(["verify", str(report_path)]) == 2
    assert "key" in capsys.readouterr().err


def test_verify_accepts_a_qknot_signature_without_a_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("qknot.signing.sign")
    from agentshield.report.schema import ReportBody, SignedReport, canonical_bytes
    from agentshield.report.signing import QKnotSigner

    body = ReportBody(
        agent_id="careful",
        scenario_pack_hash="abc",
        policy_version=1,
        created_at="2026-10-02T00:00:00Z",
        scenarios=[],
        trace_refs=[],
    )
    signed = SignedReport(
        report=body,
        signature=QKnotSigner(b"b" * 32).sign(canonical_bytes(body)),
        algorithm="qknot",
    )
    report_path = tmp_path / "report.json"
    report_path.write_text(signed.model_dump_json(), encoding="utf-8")
    assert main(["verify", str(report_path)]) == 0
    assert "signature matches" in capsys.readouterr().out


def test_verify_rejects_a_tampered_qknot_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("qknot.signing.sign")
    from agentshield.report.schema import ReportBody, SignedReport, canonical_bytes
    from agentshield.report.signing import QKnotSigner

    body = ReportBody(
        agent_id="careful",
        scenario_pack_hash="abc",
        policy_version=1,
        created_at="2026-10-02T00:00:00Z",
        scenarios=[],
        trace_refs=[],
    )
    signed = SignedReport(
        report=body,
        signature=QKnotSigner(b"c" * 32).sign(canonical_bytes(body)),
        algorithm="qknot",
    )
    dumped = signed.model_dump(mode="json")
    dumped["report"]["agent_id"] = "leaky"
    report_path = tmp_path / "report.json"
    report_path.write_text(__import__("json").dumps(dumped), encoding="utf-8")
    assert main(["verify", str(report_path)]) == 1
    assert "does not match" in capsys.readouterr().out


def test_scenarios_empty_dir_exits_with_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["scenarios", "--dir", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert "directory" in error
    assert "no scenario files" in error
