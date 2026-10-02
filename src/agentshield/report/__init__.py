"""Signed reports: canonical body, signatures, and a single HTML file."""

from agentshield.report.render import render_html
from agentshield.report.schema import (
    FailingRule,
    ReportBody,
    ScenarioOutcome,
    TraceRef,
    canonical_bytes,
    content_hash,
    scenario_pack_hash,
    trace_ref,
)
from agentshield.report.signing import (
    ML_DSA_ALG,
    QKNOT_ALG,
    LocalSigner,
    QKnotSigner,
    Signer,
    qknot_verify,
    sign,
    verify,
)

__all__ = [
    "ML_DSA_ALG",
    "QKNOT_ALG",
    "FailingRule",
    "LocalSigner",
    "QKnotSigner",
    "ReportBody",
    "ScenarioOutcome",
    "Signer",
    "TraceRef",
    "canonical_bytes",
    "content_hash",
    "qknot_verify",
    "render_html",
    "scenario_pack_hash",
    "sign",
    "trace_ref",
    "verify",
]
