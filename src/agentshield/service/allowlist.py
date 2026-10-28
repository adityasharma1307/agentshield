"""Which agents and which files `POST /runs` may name.

A run imports `agent` as code and reads `suite` and `policy` from disk, so an
open endpoint is remote code execution and a file-read oracle. The service
accepts an agent only when it matches `AGENTSHIELD_ALLOWED_AGENTS` and paths
only when they resolve under `AGENTSHIELD_ALLOWED_ROOTS`.

`AGENTSHIELD_ALLOWED_AGENTS` is a comma-separated list. An entry is an exact
`module:attribute`, or `package.*` for any module in that package. Unset or
empty allows no agent.

`AGENTSHIELD_ALLOWED_ROOTS` is a list of directories separated by
`os.pathsep`. Unset means the installed `agentshield` package directory, which
holds the shipped suites and the default policy. Paths are compared after
`Path.resolve()`, so a symlink cannot point outside a root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import agentshield


def shipped_root() -> Path:
    """The installed package directory: shipped suites and the default policy."""
    return Path(agentshield.__file__).resolve().parent


@dataclass(frozen=True)
class RunAllowlist:
    """Agent entry patterns and directory roots a run may use."""

    agents: tuple[str, ...]
    roots: tuple[Path, ...]

    @classmethod
    def from_env(cls) -> RunAllowlist:
        """Read `AGENTSHIELD_ALLOWED_AGENTS` and `AGENTSHIELD_ALLOWED_ROOTS`."""
        raw_agents = os.environ.get("AGENTSHIELD_ALLOWED_AGENTS", "")
        agents = tuple(item.strip() for item in raw_agents.split(",") if item.strip())
        raw_roots = os.environ.get("AGENTSHIELD_ALLOWED_ROOTS", "")
        roots = tuple(
            Path(item).expanduser().resolve() for item in raw_roots.split(os.pathsep) if item
        )
        return cls(agents=agents, roots=roots or (shipped_root(),))

    def allows_agent(self, entry: str) -> bool:
        """True when `entry` matches an exact entry or a `package.*` pattern."""
        module = entry.partition(":")[0]
        for pattern in self.agents:
            if pattern.endswith(".*"):
                package = pattern[:-2]
                if package and (module == package or module.startswith(package + ".")):
                    return True
            elif entry == pattern:
                return True
        return False

    def allows_path(self, path: Path) -> bool:
        """True when the resolved `path` is inside one of the roots."""
        resolved = path.resolve()
        return any(resolved.is_relative_to(root.resolve()) for root in self.roots)
