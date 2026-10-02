"""Load a policy file. The shape is `docs/policy-reference.md`, schema version 1."""

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Severity = Literal["low", "medium", "high", "critical"]
CheckName = Literal[
    "tool_never_called",
    "tool_called",
    "secret_not_in_output",
    "no_external_send_of",
    "regex",
    "span_sequence",
    "llm_judge",
]
RegexTarget = Literal["model_output", "tool_args"]

_COMMON = frozenset({"id", "description", "severity", "check", "tags"})
_PARAMETERS: dict[str, frozenset[str]] = {
    "tool_never_called": frozenset({"tool"}),
    "tool_called": frozenset({"tool"}),
    "secret_not_in_output": frozenset({"secret"}),
    "no_external_send_of": frozenset({"category"}),
    "regex": frozenset({"pattern", "target"}),
    "span_sequence": frozenset({"forbidden"}),
    "llm_judge": frozenset({"rubric", "samples"}),
}


class PolicyLoadError(Exception):
    """A policy mapping or file failed to load."""

    def __init__(
        self,
        message: str,
        *,
        path: Path | None,
        field: str,
        line: int | None = None,
    ) -> None:
        self.path = path
        self.field = field
        self.line = line
        location = "<memory>" if path is None else str(path)
        if line is not None:
            location = f"{location}:{line}"
        super().__init__(f"{location}: {field}: {message}")


class Rule(BaseModel):
    """One policy rule. Parameters that do not belong to `check` are rejected."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: Severity
    check: CheckName
    tags: list[str] = Field(default_factory=list)
    tool: str | None = None
    secret: str | None = None
    category: str | None = None
    pattern: str | None = None
    target: RegexTarget | None = None
    forbidden: list[str] | None = None
    rubric: str | None = None
    samples: int | None = None

    @model_validator(mode="after")
    def _parameters_match_the_check(self) -> Self:
        if self.check in {"tool_never_called", "tool_called"} and not self.tool:
            raise ValueError(f"{self.check} requires tool")
        if self.check == "secret_not_in_output" and not self.secret:
            raise ValueError("secret_not_in_output requires secret")
        if self.check == "no_external_send_of" and not self.category:
            raise ValueError("no_external_send_of requires category")
        if self.check == "regex":
            if not self.pattern or self.target is None:
                raise ValueError("regex requires pattern and target")
            _compile_pattern(self.pattern)
        if self.check == "span_sequence" and not self.forbidden:
            raise ValueError("span_sequence requires forbidden")
        if self.check == "llm_judge":
            if not self.rubric or self.samples is None:
                raise ValueError("llm_judge requires rubric and samples")
            if self.samples < 3 or self.samples % 2 == 0:
                raise ValueError("llm_judge samples must be an odd integer of at least 3")
        return self


class Policy(BaseModel):
    """A versioned list of rules. Version 1 is the only accepted schema."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> Self:
        seen: set[str] = set()
        for rule in self.rules:
            if rule.id in seen:
                raise ValueError(f"duplicate rule id {rule.id!r}")
            seen.add(rule.id)
        return self


def parse_policy(data: object, *, path: Path | None = None) -> Policy:
    """Validate a policy mapping."""
    if not isinstance(data, dict):
        raise PolicyLoadError("policy must be a mapping", path=path, field="policy")
    _precheck(data, path=path)
    try:
        return Policy.model_validate(data)
    except ValidationError as exc:
        field, message = _validation_error_parts(exc)
        raise PolicyLoadError(message, path=path, field=field) from exc


def load_policy(path: Path) -> Policy:
    """Load one policy file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyLoadError(str(exc), path=path, field="policy") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line_number = getattr(mark, "line", None)
        line = line_number + 1 if isinstance(line_number, int) else None
        problem = getattr(exc, "problem", None) or str(exc)
        raise PolicyLoadError(str(problem), path=path, field="yaml", line=line) from exc
    return parse_policy(data, path=path)


def load_default_policy() -> Policy:
    """The policy shipped with the package."""
    return load_policy(Path(__file__).resolve().parent / "default_policy.yaml")


def _precheck(data: dict[str, Any], *, path: Path | None) -> None:
    rules = data.get("rules")
    if rules is None:
        return
    if not isinstance(rules, list):
        raise PolicyLoadError("rules must be a list", path=path, field="rules")
    if len(rules) == 0:
        raise PolicyLoadError("rules must contain at least one rule", path=path, field="rules")
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise PolicyLoadError("a rule must be a mapping", path=path, field="rules")
        rule_id = rule.get("id")
        if isinstance(rule_id, str) and rule_id in seen:
            raise PolicyLoadError(f"duplicate rule id {rule_id!r}", path=path, field="id")
        if isinstance(rule_id, str):
            seen.add(rule_id)
        check = rule.get("check")
        if not isinstance(check, str) or check not in _PARAMETERS:
            continue
        allowed = _COMMON | _PARAMETERS[check]
        for key in rule:
            if key not in allowed:
                raise PolicyLoadError(
                    f"{key!r} is not a parameter of {check}",
                    path=path,
                    field=str(key),
                )
        for key in _PARAMETERS[check]:
            if rule.get(key) in (None, "", []):
                raise PolicyLoadError(f"{check} requires {key}", path=path, field=key)


def _compile_pattern(pattern: str) -> None:
    import re

    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid regex: {exc}") from exc


def _validation_error_parts(exc: ValidationError) -> tuple[str, str]:
    err = exc.errors()[0]
    loc = [str(part) for part in err.get("loc", ()) if not str(part).isdigit()]
    field = loc[-1] if loc else "policy"
    message = str(err.get("msg", "invalid policy"))
    if message.startswith("Value error, "):
        message = message[len("Value error, ") :]
    err_type = str(err.get("type", ""))
    if err_type == "extra_forbidden":
        message = f"unknown field {field!r}"
    elif err_type == "missing":
        message = f"{field} is required"
    elif err_type == "literal_error" and field == "version":
        message = f"unsupported policy version {err.get('input')!r}"
    elif err_type == "literal_error" and field == "severity":
        message = f"unknown severity {err.get('input')!r}"
    elif "duplicate rule id" in message:
        field = "id"
    return field, message
