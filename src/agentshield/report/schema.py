"""The signed report body and its canonical JSON encoding.

The signature covers `canonical_bytes` of the body. A one-byte change in that
encoding is a different payload.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FailingRule(BaseModel):
    """One rule that failed for a scenario."""

    model_config = ConfigDict(extra="forbid")

    id: str
    severity: str
    reason: str


class ScenarioOutcome(BaseModel):
    """Pass or fail for one scenario, plus the rule ids and excerpt a reviewer needs."""

    model_config = ConfigDict(extra="forbid")

    id: str
    suite: str
    passed: bool
    deciding_event: int | None = None
    reason: str = ""
    failing_rules: list[FailingRule] = Field(default_factory=list)
    excerpt: str = ""


class TraceRef(BaseModel):
    """Sha256 of one scenario's canonical trace JSON."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    sha256: str


class ReportBody(BaseModel):
    """The bytes that get signed. Fields are the Phase 6 schema."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    scenario_pack_hash: str
    policy_version: int
    created_at: str
    scenarios: list[ScenarioOutcome]
    trace_refs: list[TraceRef]


class SignedReport(BaseModel):
    """A report body plus the signature over its canonical bytes."""

    model_config = ConfigDict(extra="forbid")

    report: ReportBody
    signature: str
    algorithm: Literal["local", "ML-DSA-44", "qknot"]


def canonical_bytes(value: object) -> bytes:
    """UTF-8 JSON with sorted keys and compact separators."""
    payload = _json_ready(value)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def content_hash(value: object) -> str:
    """Hex sha256 of `canonical_bytes`."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def scenario_pack_hash(directory: Path) -> str:
    """Sha256 of the scenario files under `directory`, sorted by relative path.

    Each file contributes its POSIX relative path, a NUL, its raw bytes, and a NUL.
    """
    files = sorted(path for path in directory.rglob("*.yaml") if path.is_file())
    hasher = hashlib.sha256()
    for path in files:
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        hasher.update(relative)
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def trace_ref(scenario_id: str, trace: object) -> TraceRef:
    """A trace reference. `trace` is an object with `model_dump` or a mapping."""
    return TraceRef(scenario_id=scenario_id, sha256=content_hash(trace))


def _json_ready(value: object) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value
