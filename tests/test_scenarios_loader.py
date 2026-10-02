"""Tests for the YAML scenario loader."""

from pathlib import Path

import pytest

from agentshield.scenarios.dsl import ScenarioLoadError
from agentshield.scenarios.loader import load_scenario_file, load_scenarios

_VALID = """\
id: sample-one
suite: injection
task: Use read_file with path="notes.txt".
tools:
  - name: read_file
    result: hello
expect:
  tool_never_called: send_email
"""


def _write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_file_loads(tmp_path: Path) -> None:
    path = _write(tmp_path, "sample.yaml", _VALID)
    scenario = load_scenario_file(path)
    assert scenario.id == "sample-one"
    assert scenario.source == path
    assert scenario.expect.names() == ["tool_never_called"]


def test_nested_file_is_loaded(tmp_path: Path) -> None:
    _write(tmp_path, "injection/sample.yaml", _VALID)
    scenarios = load_scenarios(tmp_path)
    assert [scenario.id for scenario in scenarios] == ["sample-one"]


def test_missing_expect(tmp_path: Path) -> None:
    text = "id: sample-one\nsuite: injection\ntask: hello\ntools: []\n"
    path = _write(tmp_path, "missing.yaml", text)
    with pytest.raises(ScenarioLoadError) as caught:
        load_scenario_file(path)
    assert caught.value.field == "expect"
    assert path.name in str(caught.value)


def test_bad_suite_names_the_file_and_field(tmp_path: Path) -> None:
    text = _VALID.replace("suite: injection", "suite: malware")
    path = _write(tmp_path, "bad.yaml", text)
    with pytest.raises(ScenarioLoadError) as caught:
        load_scenario_file(path)
    assert caught.value.field == "suite"
    assert str(path) in str(caught.value)
    assert "unknown suite" in str(caught.value)


def test_duplicate_id_names_the_second_file(tmp_path: Path) -> None:
    _write(tmp_path, "a/one.yaml", _VALID)
    second = _write(tmp_path, "b/two.yaml", _VALID)
    with pytest.raises(ScenarioLoadError) as caught:
        load_scenarios(tmp_path)
    assert caught.value.field == "id"
    assert caught.value.path == second
    assert "duplicate id" in str(caught.value)


def test_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ScenarioLoadError) as caught:
        load_scenarios(tmp_path)
    assert caught.value.field == "directory"
    assert "no scenario files" in str(caught.value)


def test_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    with pytest.raises(ScenarioLoadError) as caught:
        load_scenarios(missing)
    assert caught.value.field == "directory"
    assert "not a directory" in str(caught.value)


def test_yaml_syntax_error_includes_the_line(tmp_path: Path) -> None:
    path = _write(tmp_path, "broken.yaml", "id: [\n")
    with pytest.raises(ScenarioLoadError) as caught:
        load_scenario_file(path)
    assert caught.value.field == "yaml"
    assert caught.value.line is not None
    assert f":{caught.value.line}:" in str(caught.value)
    assert str(path) in str(caught.value)
