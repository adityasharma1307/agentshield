"""Checks for the HMAC signing key. No default key exists.

This module imports nothing from `agentshield`, so `config` and `report`
can both use it without an import cycle.
"""

import os
import stat

SIGNING_SECRET_ENV = "AGENTSHIELD_SIGNING_SECRET"
SIGNING_SECRET_FILE_ENV = "AGENTSHIELD_SIGNING_SECRET_FILE"
MIN_LOCAL_SECRET_BYTES = 32
# Values that were published as defaults or look like placeholders. A key that
# contains one of these is refused even when it is long enough.
_WEAK_MARKERS = (
    b"agentshield-local-dev",
    b"changeme",
    b"change-me",
    b"change_me",
    b"replace-me",
    b"replace_me",
    b"your-secret",
    b"your_secret",
    b"placeholder",
)


class SigningKeyError(ValueError):
    """The HMAC signing key is missing, too short, or a known placeholder."""


def check_local_secret(secret: bytes) -> bytes:
    """Return `secret` when it is usable as an HMAC key. Raise otherwise.

    The error never contains the key.
    """
    if not secret or not secret.strip():
        raise SigningKeyError(
            f"no signing key: set {SIGNING_SECRET_ENV} to a random value of at least "
            f"{MIN_LOCAL_SECRET_BYTES} bytes, for example `openssl rand -hex 32`"
        )
    lowered = secret.lower()
    if any(marker in lowered for marker in _WEAK_MARKERS):
        raise SigningKeyError(
            "refusing a known default or placeholder signing key; "
            "generate one with `openssl rand -hex 32`"
        )
    if len(secret) < MIN_LOCAL_SECRET_BYTES:
        raise SigningKeyError(
            f"signing key is {len(secret)} bytes; at least {MIN_LOCAL_SECRET_BYTES} are required"
        )
    if len(set(secret)) < 8:
        raise SigningKeyError("signing key has too few distinct bytes to be random")
    return secret


def check_secret_file_stat(st: os.stat_result, worker_uid: int) -> None:
    """Raise `SigningKeyError` unless `st` is a regular file only its owner can read.

    The owner must be `worker_uid` or root. Group and other bits must be clear,
    so mode 0600 or 0400.
    """
    if not stat.S_ISREG(st.st_mode):
        raise SigningKeyError(f"{SIGNING_SECRET_FILE_ENV} must name a regular file")
    if st.st_mode & 0o077:
        raise SigningKeyError(
            f"{SIGNING_SECRET_FILE_ENV} is readable by group or others "
            f"(mode {stat.S_IMODE(st.st_mode):04o}); chmod 600 it"
        )
    if st.st_uid not in (worker_uid, 0):
        raise SigningKeyError(
            f"{SIGNING_SECRET_FILE_ENV} is owned by uid {st.st_uid}, "
            f"not the worker (uid {worker_uid}) or root"
        )


def read_secret_file(path: str) -> str:
    """Read the signing key from `path` after checking ownership and mode.

    Symlinks are refused. One trailing newline is removed. The key is checked
    with `check_local_secret`.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise SigningKeyError(
            f"cannot open {SIGNING_SECRET_FILE_ENV} ({type(exc).__name__}, errno {exc.errno})"
        ) from None
    try:
        if os.name == "posix":
            check_secret_file_stat(os.fstat(fd), os.geteuid())
        raw = b""
        while chunk := os.read(fd, 4096):
            raw += chunk
            if len(raw) > 65536:
                raise SigningKeyError(f"{SIGNING_SECRET_FILE_ENV} is too large")
    finally:
        os.close(fd)
    if raw.endswith(b"\r\n"):
        raw = raw[:-2]
    elif raw.endswith(b"\n"):
        raw = raw[:-1]
    check_local_secret(raw)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise SigningKeyError(f"{SIGNING_SECRET_FILE_ENV} must hold UTF-8 text") from None
