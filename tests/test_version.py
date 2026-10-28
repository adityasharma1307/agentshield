"""Tests for the package version."""

import re
from importlib.metadata import PackageNotFoundError, version

import pytest

from agentshield import __version__


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_distribution_version_matches_package() -> None:
    try:
        installed = version("agsh")
    except PackageNotFoundError:
        pytest.skip("agsh is not installed")
    assert installed == __version__
