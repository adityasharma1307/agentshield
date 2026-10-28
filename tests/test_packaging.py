"""The sdist ships a fixed file list, and release installs are hash-locked."""

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_REQUIREMENTS = _ROOT / ".github" / "requirements"


def test_sdist_has_an_explicit_include_list() -> None:
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert "/src/agentshield" in include
    for excluded in ("frontend", "results", "docker", ".github"):
        assert not any(excluded in entry for entry in include)


def test_every_locked_release_requirement_is_pinned_and_hashed() -> None:
    for name in ("release-tools.txt", "release-runtime.txt"):
        text = (_REQUIREMENTS / name).read_text(encoding="utf-8")
        blocks = re.split(r"\n(?=[a-z0-9])", text.split("\n", 2)[2])
        pins = [block for block in blocks if block.strip() and not block.startswith("#")]
        assert pins, name
        for block in pins:
            assert re.match(r"^[a-z0-9._-]+==\S+ \\", block), block.splitlines()[0]
            assert "--hash=sha256:" in block, block.splitlines()[0]


def test_release_build_installs_only_from_the_locks() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "--require-hashes --no-deps -r .github/requirements/release-tools.txt" in workflow
    assert "--require-hashes --no-deps -r .github/requirements/release-runtime.txt" in workflow
    assert "python -m build --no-isolation" in workflow
    assert "pip install --upgrade pip build twine" not in workflow


def test_release_image_build_uses_no_cache() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "cache-from" not in workflow
    assert "no-cache: true" in workflow
