"""Low-entropy keys are refused even at 32+ bytes; generated keys are not (R2)."""

import base64
import secrets

import pytest

from agentshield.signing_key import SigningKeyError, check_local_secret

_WEAK = [
    "abcdefghabcdefghabcdefghabcdefgh",  # one 8-byte unit repeated
    "0123456789abcdef0123456789abcdef",  # a run, repeated
    "abcdefghijklmnopqrstuvwxyzABCDEF",  # an alphabet run
    "password-password-password-12345",  # a word repeated
    "Tr0ub4dor&3Tr0ub4dor&3Tr0ub4dor&",  # a passphrase repeated
    "aaaabbbbccccddddeeeeffffgggghhhh",  # long same-byte runs
    "zyxwvutsrqponmlkjihgfedcbaZYXWVU",  # a descending run
]


@pytest.mark.parametrize("key", _WEAK)
def test_low_entropy_keys_are_refused(key: str) -> None:
    assert len(key) >= 32
    with pytest.raises(SigningKeyError) as caught:
        check_local_secret(key.encode())
    assert key not in str(caught.value)


@pytest.mark.parametrize(
    "make",
    [
        lambda: secrets.token_hex(32),
        lambda: secrets.token_hex(16),
        lambda: secrets.token_urlsafe(32),
        lambda: base64.b64encode(secrets.token_bytes(24)).decode(),
    ],
    ids=["openssl-rand-hex-32", "hex-16", "urlsafe-32", "openssl-rand-base64-24"],
)
def test_generated_keys_are_accepted(make: object) -> None:
    assert callable(make)
    for _ in range(2000):
        key = make()
        check_local_secret(key.encode())
