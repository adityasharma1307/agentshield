"""Sign and verify the canonical report bytes.

`LocalSigner` is the signer the default CI tests use. It is not ML-DSA.
`sign` and `verify` are ML-DSA-44 through liboqs and require the `pq` extra.
`QKnotSigner` is Ed25519 plus ML-DSA-87 through qknot and requires the `qknot` extra.
"""

import hashlib
import hmac
import json
from typing import Any, Literal, Protocol

ML_DSA_ALG: Literal["ML-DSA-44"] = "ML-DSA-44"
QKNOT_ALG: Literal["qknot"] = "qknot"
QKNOT_CONTEXT = b"agentshield-report"
QKNOT_SUBJECT = "agentshield-report"


class Signer(Protocol):
    """A signer small enough to move into a shared library later."""

    def sign(self, payload: bytes) -> str:
        """Return the signature for `payload`."""

    def verify(self, payload: bytes, signature: str) -> bool:
        """Return whether `signature` matches `payload`."""


class LocalSigner:
    """HMAC-SHA256 over the payload. Not ML-DSA."""

    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def sign(self, payload: bytes) -> str:
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        expected = self.sign(payload)
        return hmac.compare_digest(expected, signature)


class QKnotSigner:
    """Hybrid Ed25519 + ML-DSA-87 over the payload, via qknot.

    `seed` is mixed only into key generation. Pass at least 32 bytes so
    keygen stays offline. Verification reads the public keys from the bundle
    qknot returns. A match means those keys signed these bytes. It does not
    name the person who holds the seed.
    """

    def __init__(self, seed: bytes) -> None:
        if len(seed) < 32:
            raise ValueError("qknot seed must be at least 32 bytes")
        self._seed = seed

    def sign(self, payload: bytes) -> str:
        """Return the qknot bundle JSON for `payload`."""
        signing, backends, bundle = _qknot()
        keys = signing.keygen(seed=self._seed)
        signed = signing.sign(
            payload,
            keys,
            exposure=backends.Exposure.OFFLINE,
            context=QKNOT_CONTEXT,
            subject_name=QKNOT_SUBJECT,
            deterministic=True,
        )
        raw = bundle.build_bundle(signed)
        return json.dumps(raw, sort_keys=True, separators=(",", ":"))

    def verify(self, payload: bytes, signature: str) -> bool:
        """Return whether `signature` is a qknot bundle over `payload`."""
        return qknot_verify(payload, signature)


def qknot_verify(payload: bytes, signature: str) -> bool:
    """Verify a qknot bundle. The public keys are inside `signature`.

    Requires the `qknot` extra. Returns false when the bundle is malformed
    or the bytes do not match. A true result does not identify the signer.
    """
    signing, _, bundle = _qknot()
    try:
        parsed = json.loads(signature)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    try:
        artefact = bundle.parse_bundle(parsed)
        report = signing.verify(
            payload,
            artefact,
            mode=signing.VerifyMode.STRICT,
            context=QKNOT_CONTEXT,
        )
    except (signing.VerificationFailed, ValueError):
        return False
    verified = report.get("verified")
    return verified is True


def sign(payload: bytes, secret_key: bytes) -> str:
    """ML-DSA signature, hex encoded. Requires the `pq` extra."""
    oqs = _liboqs()
    with oqs.Signature(ML_DSA_ALG, secret_key) as signer:
        raw = signer.sign(payload)
    if not isinstance(raw, bytes):
        raise TypeError("ML-DSA sign did not return bytes")
    return raw.hex()


def verify(payload: bytes, signature: str, public_key: bytes) -> bool:
    """Return whether an ML-DSA signature matches. Requires the `pq` extra."""
    oqs = _liboqs()
    with oqs.Signature(ML_DSA_ALG) as verifier:
        return bool(verifier.verify(payload, bytes.fromhex(signature), public_key))


def _liboqs() -> Any:
    try:
        import oqs
    except ImportError as exc:
        raise ImportError("ML-DSA requires the agentshield[pq] extra") from exc
    return oqs


def _qknot() -> tuple[Any, Any, Any]:
    try:
        import qknot.signing.backends as backends
        import qknot.signing.bundle as bundle
        import qknot.signing.sign as signing
    except ImportError as exc:
        raise ImportError(
            "qknot signing requires the agentshield[qknot] extra "
            "(https://github.com/adityasharma1307/qknot)"
        ) from exc
    return signing, backends, bundle
