"""
The ONE real channel. Uses smtplib against a configured SMTP server --
genuinely dispatches over the real protocol, not a declared simulator.
Connection factory is injectable (same pluggable-transport pattern as
razorpay_client.py) specifically so this is testable without a live
SMTP server; real credentials (SMTP_HOST/PORT/USER/PASSWORD) wire in
via app/config.py in the deployed repo.

Idempotency: smtplib has no native idempotency concept. The
idempotency_key is attached as an informational header only -- actual
duplicate-send prevention lives entirely in
execution/outbox.py::InterventionAttempt.idempotency_key (a DB UNIQUE
constraint). This function does NOT itself guard against sending
twice if called twice; that guarantee belongs upstream, and pretending
otherwise here would be exactly the kind of duplicated, drifting
enforcement logic AGENT-SECURITY.md warns against.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from typing import Callable

from .base import ChannelSendResult

channel_name = "email"
is_simulated = False

SMTPConnectionFactory = Callable[[], smtplib.SMTP]


def _default_connection_factory() -> smtplib.SMTP:
    host = os.getenv("SMTP_HOST", "localhost")
    port = int(os.getenv("SMTP_PORT", "587"))
    conn = smtplib.SMTP(host, port, timeout=10)
    conn.starttls()
    user, pw = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    if user and pw:
        conn.login(user, pw)
    return conn


def send(
    recipient: str, subject: str, body: str, idempotency_key: str,
    from_address: str = "noreply@merchant.test",
    connection_factory: SMTPConnectionFactory = _default_connection_factory,
) -> ChannelSendResult:
    """
    Raises smtplib.SMTPException upward on failure -- deliberately not
    caught here. The outbox worker's retry/backoff and the RUNBOOK's
    "Razorpay 5xx -> breaker opens" pattern both assume failures
    propagate to be handled at the orchestration layer, not swallowed
    silently inside a channel adapter.
    """
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = recipient
    msg["X-Idempotency-Key"] = idempotency_key

    conn = connection_factory()
    try:
        conn.sendmail(from_address, [recipient], msg.as_string())
    finally:
        try:
            conn.quit()
        except Exception:
            pass

    return ChannelSendResult(
        sent=True, channel=channel_name, idempotency_key=idempotency_key,
        provider_message_id=None, is_simulated=False, raw_response={"status": "sent"},
    )
