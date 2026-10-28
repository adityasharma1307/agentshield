"""Run the agent child as a separate, unprivileged OS user.

Set `AGENTSHIELD_AGENT_USER` (a user name or a numeric uid) and, optionally,
`AGENTSHIELD_AGENT_GROUP`. The worker then starts the agent child with that
uid and gid and no supplementary groups. Files that only the worker's user can
read, such as a 0600 signing key, are then out of the agent's reach, and so is
`/proc/<worker>`.

This fails closed. When a user is requested but can't be applied, because the
platform is not POSIX, the user is unknown, it is root or the worker's own
user, or the worker lacks the privilege to switch, `AgentUserError` is raised
and no agent runs.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

AGENT_USER_ENV = "AGENTSHIELD_AGENT_USER"
AGENT_GROUP_ENV = "AGENTSHIELD_AGENT_GROUP"

# Linux capability bit numbers (include/uapi/linux/capability.h).
_CAP_SETGID = 6
_CAP_SETUID = 7


class AgentUserError(RuntimeError):
    """Separate-user isolation was requested and can't be applied."""


@dataclass(frozen=True)
class AgentIdentity:
    """The uid and gid the agent child runs as."""

    uid: int
    gid: int
    name: str | None = None
    home: str | None = None


def resolve_agent_identity(
    user: str, group: str | None = None, *, worker_uid: int | None = None
) -> AgentIdentity:
    """Look up `user` (name or uid) and `group` (name or gid).

    Raises `AgentUserError` for an unknown user or group, root, or the worker's
    own uid. Without `group`, the user's primary group is used; gid 0 is refused.
    """
    if os.name != "posix":
        raise AgentUserError(f"{AGENT_USER_ENV} needs a POSIX system")
    import grp
    import pwd

    user = user.strip()
    if not user:
        raise AgentUserError(f"{AGENT_USER_ENV} is set but empty")
    try:
        entry = pwd.getpwuid(int(user)) if user.isdigit() else pwd.getpwnam(user)
    except (KeyError, OverflowError) as exc:
        if not user.isdigit():
            raise AgentUserError(f"{AGENT_USER_ENV}: no such user {user!r}") from exc
        uid, name, home, primary_gid = int(user), None, None, None
    else:
        uid, name, home, primary_gid = entry.pw_uid, entry.pw_name, entry.pw_dir, entry.pw_gid
    if group is not None and group.strip():
        group = group.strip()
        try:
            gid = grp.getgrgid(int(group)).gr_gid if group.isdigit() else grp.getgrnam(group).gr_gid
        except (KeyError, OverflowError) as exc:
            if not group.isdigit():
                raise AgentUserError(f"{AGENT_GROUP_ENV}: no such group {group!r}") from exc
            gid = int(group)
    elif primary_gid is not None:
        gid = primary_gid
    else:
        raise AgentUserError(f"uid {uid} has no passwd entry; set {AGENT_GROUP_ENV} as well")
    if uid == 0:
        raise AgentUserError(f"{AGENT_USER_ENV} must not be root")
    if gid == 0:
        raise AgentUserError(f"{AGENT_GROUP_ENV} must not be gid 0")
    current = os.geteuid() if worker_uid is None else worker_uid
    if uid == current:
        raise AgentUserError(
            f"{AGENT_USER_ENV} is the worker's own uid ({uid}); pick a separate user"
        )
    return AgentIdentity(uid=uid, gid=gid, name=name, home=home)


def agent_identity_from_env(environ: Mapping[str, str] | None = None) -> AgentIdentity | None:
    """The identity `AGENTSHIELD_AGENT_USER` asks for, or `None` when it is unset."""
    env = os.environ if environ is None else environ
    user = env.get(AGENT_USER_ENV)
    if user is None:
        return None
    return resolve_agent_identity(user, env.get(AGENT_GROUP_ENV))


def can_switch_user() -> bool:
    """Whether this process may start a child under another uid and gid."""
    if os.name != "posix":
        return False
    if os.geteuid() == 0:
        # Root still needs the capabilities (a container may drop them).
        caps = _effective_caps()
        return caps is None or _has_setid(caps)
    caps = _effective_caps()
    return caps is not None and _has_setid(caps)


def require_switch(identity: AgentIdentity) -> None:
    """Raise `AgentUserError` when the worker can't start a child as `identity`."""
    if not can_switch_user():
        raise AgentUserError(
            f"{AGENT_USER_ENV} asks for uid {identity.uid}, but the worker "
            f"(uid {os.geteuid()}) lacks CAP_SETUID/CAP_SETGID; refusing to run "
            "the agent as the worker's own user"
        )


def _has_setid(caps: int) -> bool:
    return bool(caps & (1 << _CAP_SETUID)) and bool(caps & (1 << _CAP_SETGID))


def _effective_caps() -> int | None:
    """CapEff from /proc on Linux, or `None` where that file does not exist."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        with Path("/proc/self/status").open(encoding="ascii") as status:
            for line in status:
                if line.startswith("CapEff:"):
                    return int(line.split()[1], 16)
    except OSError:
        return None
    return None
