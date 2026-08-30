"""
DECLARED SIMULATOR -- logs what would have been sent, never actually
dispatches anything. See the README's "what is real vs simulated"
table; this file's is_simulated=True is the mechanism that keeps that
table honest rather than aspirational. Swapping to a real WhatsApp
Business API integration means replacing this file's body, not its
interface -- callers never change.
"""
from __future__ import annotations

from .base import ChannelSendResult

channel_name = "whatsapp"
is_simulated = True


def send(recipient: str, subject: str, body: str, idempotency_key: str) -> ChannelSendResult:
    return ChannelSendResult(
        sent=True, channel=channel_name, idempotency_key=idempotency_key,
        provider_message_id=f"sim_wa_{idempotency_key[:12]}",
        is_simulated=True,
        raw_response={"simulated": True, "would_send_to": recipient, "body_preview": body[:80]},
    )
