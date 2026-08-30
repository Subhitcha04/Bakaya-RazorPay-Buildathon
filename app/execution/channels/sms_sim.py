"""DECLARED SIMULATOR -- see whatsapp_sim.py for the full rationale."""
from __future__ import annotations

from .base import ChannelSendResult

channel_name = "sms"
is_simulated = True


def send(recipient: str, subject: str, body: str, idempotency_key: str) -> ChannelSendResult:
    return ChannelSendResult(
        sent=True, channel=channel_name, idempotency_key=idempotency_key,
        provider_message_id=f"sim_sms_{idempotency_key[:12]}",
        is_simulated=True,
        raw_response={"simulated": True, "would_send_to": recipient, "body_preview": body[:80]},
    )
