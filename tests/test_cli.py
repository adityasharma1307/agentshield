"""Tests for the command-line entrypoint."""

import pytest

from agentsheild import __version__
from agentsheild.cli import main


def test_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "agentsheild" in output
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
    assert capsys.readouterr().out.strip() == f"agentsheild {__version__}"


def test_unknown_flag_exits_with_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--not-a-flag"])
    assert caught.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
