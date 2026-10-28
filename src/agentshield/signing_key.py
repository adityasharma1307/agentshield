"""Checks for the HMAC signing key. No default key exists.

This module imports nothing from `agentshield`, so `config` and `report`
can both use it without an import cycle.
"""

SIGNING_SECRET_ENV = "AGENTSHIELD_SIGNING_SECRET"
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
