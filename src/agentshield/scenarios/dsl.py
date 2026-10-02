"""Scenario models and the error raised when a file cannot be loaded.

The YAML shape lives in `docs/writing-scenarios.md`. `expect` keys are check
names from `docs/policy-reference.md`. The runner evaluates the deterministic
checks. `llm_judge` stays a policy rule and is rejected here. A rejected file
raises `ScenarioLoadError` with the path and the field.
"""

import re
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    field_validator,
    model_validator,
)

SuiteName = Literal[
    "injection",
    "exfiltration",
    "scope_creep",
    "policy_violation",
    "tool_jailbreak",
]

PHASE3_CHECKS: frozenset[str] = frozenset(
    {
        "tool_never_called",
        "tool_called",
        "secret_not_in_output",
        "no_external_send_of",
        "regex",
        "span_sequence",
    }
)
UNIMPLEMENTED_CHECKS: frozenset[str] = frozenset({"llm_judge"})
KNOWN_TOOLS: frozenset[str] = frozenset(
    {"search", "read_file", "send_email", "http_get", "db_query"}
)

RegexTarget = Literal["model_output", "tool_args"]


class ScenarioLoadError(Exception):
    """A scenario mapping or file failed to load.

    `path` is the file, or `None` when the mapping was not read from disk.
    `field` is the key that failed, or `yaml` for a parse error. `line` is set
    when PyYAML reported a line.
    """

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


class Label(BaseModel):
    """A span of planted tool text marked for a policy category such as `pii`."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Step(BaseModel):
    """One tool enabled for a scenario, plus the output planted for it."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    result: str | None = None
    trap: bool = False
    trap_text: str | None = None
    documents: dict[str, str] = Field(default_factory=dict)
    labels: list[Label] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_document_keys(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("documents"), dict):
            rewritten = dict(data)
            rewritten["documents"] = {str(key): value for key, value in data["documents"].items()}
            return rewritten
        return data


class Check(BaseModel):
    """One machine-checkable expectation, in file order."""

    model_config = ConfigDict(extra="forbid")

    name: Literal[
        "tool_never_called",
        "tool_called",
        "secret_not_in_output",
        "no_external_send_of",
        "regex",
        "span_sequence",
    ]
    tool: str | None = None
    secret: str | None = None
    category: str | None = None
    pattern: str | None = None
    target: RegexTarget | None = None
    forbidden: list[str] | None = None

    @model_validator(mode="after")
    def _parameters_match_the_check(self) -> Self:
        if self.name in {"tool_never_called", "tool_called"}:
            if not self.tool:
                raise ValueError(f"{self.name} requires a tool name")
        elif self.name == "secret_not_in_output":
            if not self.secret:
                raise ValueError("secret_not_in_output requires a secret")
        elif self.name == "no_external_send_of":
            if not self.category:
                raise ValueError("no_external_send_of requires a category")
        elif self.name == "regex":
            if not self.pattern or self.target is None:
                raise ValueError("regex requires pattern and target")
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex: {exc}") from exc
        elif not self.forbidden:
            raise ValueError("span_sequence requires forbidden")
        return self


class Expectation(BaseModel):
    """The `expect` mapping. A scenario fails when any check fails."""

    model_config = ConfigDict(extra="forbid")

    checks: list[Check] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _from_mapping(cls, data: Any) -> Any:
        if not isinstance(data, dict) or set(data) == {"checks"}:
            return data
        checks: list[dict[str, Any]] = []
        for key, value in data.items():
            items = value if isinstance(value, list) else [value]
            for item in items:
                checks.append(_one_check(key, item))
        if not checks:
            raise ValueError("expect must name at least one check")
        return {"checks": checks}

    def names(self) -> list[str]:
        """Check names in file order, each name once."""
        seen: list[str] = []
        for check in self.checks:
            if check.name not in seen:
                seen.append(check.name)
        return seen


class Scenario(BaseModel):
    """One adversarial task, the tools it enables, and the checks that score it."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    suite: SuiteName
    task: str = Field(min_length=1)
    tools: list[Step] = Field(default_factory=list)
    expect: Expectation
    context: dict[str, str] = Field(default_factory=dict)
    _source: Path | None = PrivateAttr(default=None)

    @field_validator("tools")
    @classmethod
    def _known_unique_tools(cls, tools: list[Step]) -> list[Step]:
        seen: set[str] = set()
        for step in tools:
            if step.name not in KNOWN_TOOLS:
                raise ValueError(f"unknown tool {step.name!r}")
            if step.name in seen:
                raise ValueError(f"duplicate tool {step.name!r}")
            seen.add(step.name)
        return tools

    @property
    def source(self) -> Path | None:
        """The file this scenario was loaded from, when it came from a file."""
        return self._source


def parse_scenario(data: object, *, path: Path | None = None) -> Scenario:
    """Validate a scenario mapping. `path` is stored for later error messages."""
    if not isinstance(data, dict):
        raise ScenarioLoadError("scenario must be a mapping", path=path, field="scenario")
    if "expect" in data:
        _precheck_expect(data["expect"], path=path)
    try:
        scenario = Scenario.model_validate(data)
    except ValidationError as exc:
        field, message = _validation_error_parts(exc)
        raise ScenarioLoadError(message, path=path, field=field) from exc
    scenario._source = path
    return scenario


def _precheck_expect(expect: object, *, path: Path | None) -> None:
    if not isinstance(expect, dict):
        return
    for key in expect:
        if not isinstance(key, str):
            raise ScenarioLoadError("expectation names must be strings", path=path, field="expect")
        if key in UNIMPLEMENTED_CHECKS:
            raise ScenarioLoadError(
                f"expectation {key!r} cannot be checked by this runner",
                path=path,
                field=key,
            )
        if key not in PHASE3_CHECKS:
            raise ScenarioLoadError(
                f"unknown expectation {key!r}",
                path=path,
                field=key,
            )


def _one_check(key: object, item: object) -> dict[str, Any]:
    if not isinstance(key, str):
        raise ValueError("expectation names must be strings")
    if key in UNIMPLEMENTED_CHECKS:
        raise ValueError(f"expectation {key!r} cannot be checked by this runner")
    if key not in PHASE3_CHECKS:
        raise ValueError(f"unknown expectation {key!r}")
    if key in {"tool_never_called", "tool_called"}:
        if not isinstance(item, str):
            raise ValueError(f"{key} expects a tool name")
        return {"name": key, "tool": item}
    if key == "secret_not_in_output":
        if not isinstance(item, str):
            raise ValueError("secret_not_in_output expects a string")
        return {"name": key, "secret": item}
    if key == "no_external_send_of":
        if not isinstance(item, str):
            raise ValueError("no_external_send_of expects a category")
        return {"name": key, "category": item}
    if key == "span_sequence":
        if not isinstance(item, dict):
            raise ValueError("span_sequence expects a mapping with forbidden")
        return {"name": key, **item}
    if not isinstance(item, dict):
        raise ValueError("regex expects a mapping with pattern and target")
    return {"name": "regex", **item}


def _validation_error_parts(exc: ValidationError) -> tuple[str, str]:
    err = exc.errors()[0]
    loc = [str(part) for part in err.get("loc", ())]
    field = loc[0] if loc else "scenario"
    message = str(err.get("msg", "invalid scenario"))
    if message.startswith("Value error, "):
        message = message[len("Value error, ") :]
    err_type = str(err.get("type", ""))
    if err_type == "extra_forbidden":
        message = f"unknown field {field!r}"
    elif err_type == "missing":
        message = f"{field} is required"
    elif err_type == "literal_error" and field == "suite":
        message = f"unknown suite {err.get('input')!r}"
    return field, message
