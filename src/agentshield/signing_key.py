"""Checks for the HMAC signing key. No default key exists.

This module imports nothing from `agentshield`, so `config` and `report`
can both use it without an import cycle.
"""

import itertools
import math

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
    problem = _low_entropy_reason(secret)
    if problem is not None:
        raise SigningKeyError(
            f"signing key looks hand-made ({problem}); generate one with `openssl rand -hex 32`"
        )
    return secret


# Thresholds for `_low_entropy_reason`. Measured against 200,000 keys each from
# `secrets.token_hex(16)`, `token_hex(32)`, `token_urlsafe(24)`, base64 of 24
# random bytes, and 32 raw random bytes: none tripped any check. The lowest
# observed byte-frequency entropy was 94 bits (a 32-character hex key).
MIN_ESTIMATED_ENTROPY_BITS = 80.0
MAX_STEP_FRACTION = 0.6
REPEAT_WINDOW = 8


def _low_entropy_reason(secret: bytes) -> str | None:
    """Why `secret` is not random enough, or `None`.

    These are statistical checks for keys a person typed: too few bits by byte
    frequency, mostly runs of equal or adjacent bytes (`aaaa`, `abcd`, `dcba`),
    or an 8-byte stretch that repeats. They cannot recognise a long passphrase
    made of distinct words; only a generated key avoids that.
    """
    length = len(secret)
    counts: dict[int, int] = {}
    for byte in secret:
        counts[byte] = counts.get(byte, 0) + 1
    bits = -sum(count * math.log2(count / length) for count in counts.values())
    if bits < MIN_ESTIMATED_ENTROPY_BITS:
        return f"about {bits:.0f} bits by byte frequency, under {MIN_ESTIMATED_ENTROPY_BITS:.0f}"
    steps = sum(1 for left, right in itertools.pairwise(secret) if abs(left - right) <= 1)
    if steps / (length - 1) > MAX_STEP_FRACTION:
        return "mostly runs of equal or adjacent characters"
    first_seen: dict[bytes, int] = {}
    for start in range(length - REPEAT_WINDOW + 1):
        window = secret[start : start + REPEAT_WINDOW]
        earlier = first_seen.setdefault(window, start)
        if start - earlier >= REPEAT_WINDOW:
            return f"a {REPEAT_WINDOW}-character stretch repeats"
    return None
