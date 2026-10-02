"""Canonical JSON, the local signer, ML-DSA when installed, and the HTML report."""

import json

import pytest

from agentshield.report.render import render_html
from agentshield.report.schema import (
    FailingRule,
    ReportBody,
    ScenarioOutcome,
    TraceRef,
    canonical_bytes,
    content_hash,
    scenario_pack_hash,
)
from agentshield.report.signing import ML_DSA_ALG, LocalSigner, sign, verify
from agentshield.trace import AgentTrace


def _body() -> ReportBody:
    return ReportBody(
        agent_id="careful",
        scenario_pack_hash="abc",
        policy_version=1,
        created_at="2026-10-02T00:00:00Z",
        scenarios=[
            ScenarioOutcome(
                id="exfil-email-canary",
                suite="exfiltration",
                passed=False,
                deciding_event=2,
                reason="send_email called",
                failing_rules=[
                    FailingRule(
                        id="no-outbound-mail",
                        severity="high",
                        reason="send_email called at event 2",
                    )
                ],
                excerpt="body=CANARY-7f3a",
            )
        ],
        trace_refs=[TraceRef(scenario_id="exfil-email-canary", sha256="def")],
    )


def test_canonical_json_is_sorted_and_compact() -> None:
    encoded = canonical_bytes({"b": 1, "a": {"d": 2, "c": 3}})
    assert encoded == b'{"a":{"c":3,"d":2},"b":1}'


def test_scenario_pack_hash_follows_sorted_paths(tmp_path: object) -> None:
    from pathlib import Path

    root = tmp_path if isinstance(tmp_path, Path) else Path(str(tmp_path))
    (root / "b").mkdir()
    (root / "a").mkdir()
    (root / "b" / "two.yaml").write_text("id: two\n", encoding="utf-8")
    (root / "a" / "one.yaml").write_text("id: one\n", encoding="utf-8")
    assert scenario_pack_hash(root) == scenario_pack_hash(root)
    assert len(scenario_pack_hash(root)) == 64


def test_local_signer_rejects_a_one_byte_change() -> None:
    signer = LocalSigner(b"test-secret")
    payload = canonical_bytes(_body())
    signature = signer.sign(payload)
    assert signer.verify(payload, signature) is True
    tampered = bytearray(payload)
    tampered[0] ^= 0x01
    assert signer.verify(bytes(tampered), signature) is False


def test_html_contains_the_failing_rule_and_no_remote_assets() -> None:
    html = render_html(_body())
    assert "no-outbound-mail" in html
    assert "Fail" in html
    assert "body=CANARY-7f3a" in html
    assert "<script" not in html
    assert "cdn" not in html.lower()
    assert "http://" not in html
    assert "https://" not in html


def test_trace_ref_is_the_canonical_trace_hash() -> None:
    trace = AgentTrace.model_validate(
        {"events": [{"sequence": 0, "kind": "final", "text": "done"}], "final_text": "done"}
    )
    assert content_hash(trace) == content_hash(json.loads(canonical_bytes(trace)))


def test_qknot_signer_rejects_a_one_byte_change() -> None:
    pytest.importorskip("qknot.signing.sign")
    from agentshield.report.schema import SignedReport
    from agentshield.report.signing import QKNOT_ALG, QKnotSigner

    signer = QKnotSigner(b"a" * 32)
    payload = canonical_bytes(_body())
    signature = signer.sign(payload)
    signed = SignedReport(report=_body(), signature=signature, algorithm=QKNOT_ALG)
    assert signed.algorithm == "qknot"
    assert signer.verify(payload, signature) is True
    tampered = bytearray(payload)
    tampered[0] ^= 0x01
    assert signer.verify(bytes(tampered), signature) is False


def test_mldsa_round_trip_when_liboqs_imports() -> None:
    oqs = pytest.importorskip("oqs")
    with oqs.Signature(ML_DSA_ALG) as signer:
        public_key = signer.generate_keypair()
        secret_key = signer.export_secret_key()
    payload = b"agentshield-report"
    signature = sign(payload, secret_key)
    assert verify(payload, signature, public_key) is True
    assert verify(payload + b"x", signature, public_key) is False
