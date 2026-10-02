"""Load a directory of scenario YAML files.

The walk is recursive and only picks up `*.yaml`. Error messages name the
file, the field, and the YAML line when PyYAML reported one.
"""

from pathlib import Path

import yaml

from agentshield.scenarios.dsl import Scenario, ScenarioLoadError, parse_scenario


def shipped_suites_dir() -> Path:
    """The directory of scenario files shipped inside the package."""
    return Path(__file__).resolve().parent / "suites"


def load_scenario_file(path: Path) -> Scenario:
    """Load one scenario file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioLoadError(str(exc), path=path, field="scenario") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line_number = getattr(mark, "line", None)
        line = line_number + 1 if isinstance(line_number, int) else None
        problem = getattr(exc, "problem", None) or str(exc)
        raise ScenarioLoadError(str(problem), path=path, field="yaml", line=line) from exc
    return parse_scenario(data, path=path)


def load_scenarios(directory: Path) -> list[Scenario]:
    """Load every `*.yaml` file under `directory`, sorted by scenario id.

    Raises `ScenarioLoadError` when the directory is missing, contains no
    scenario files, or two files share an id.
    """
    if not directory.is_dir():
        raise ScenarioLoadError("not a directory", path=directory, field="directory")
    files = sorted(path for path in directory.rglob("*.yaml") if path.is_file())
    if not files:
        raise ScenarioLoadError("no scenario files found", path=directory, field="directory")
    scenarios: list[Scenario] = []
    seen: dict[str, Path] = {}
    for path in files:
        scenario = load_scenario_file(path)
        previous = seen.get(scenario.id)
        if previous is not None:
            raise ScenarioLoadError(
                f"duplicate id {scenario.id!r} (also defined in {previous})",
                path=path,
                field="id",
            )
        seen[scenario.id] = path
        scenarios.append(scenario)
    scenarios.sort(key=lambda scenario: scenario.id)
    return scenarios
