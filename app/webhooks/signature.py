"""
HMAC-SHA256 verification of Razorpay webhook signatures.

Constant-time comparison via hmac.compare_digest -- a naive `==` on the
digests leaks timing information about how many leading bytes matched,
which is a real (if niche) side-channel on a payments endpoint. Non-
negotiable on this path.
"""
from __future__ import annotations

import hashlib
import hmac


def verify_signature(payload_body: bytes, signature_header: str, webhook_secret: str) -> bool:
    if not signature_header or not webhook_secret:
        return False
    expected = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
