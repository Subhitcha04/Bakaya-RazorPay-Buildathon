"""DECLARED SIMULATOR -- see whatsapp_sim.py for the full rationale.
Explicitly out of scope for real integration per the plan's cut list:
voice needs days of ElevenLabs/Exotel integration for one demo clip."""
from __future__ import annotations

from .base import ChannelSendResult

channel_name = "voice"
is_simulated = True


def send(recipient: str, subject: str, body: str, idempotency_key: str) -> ChannelSendResult:
    return ChannelSendResult(
        sent=True, channel=channel_name, idempotency_key=idempotency_key,
        provider_message_id=f"sim_voice_{idempotency_key[:12]}",
        is_simulated=True,
        raw_response={"simulated": True, "would_call": recipient, "script_preview": body[:80]},
    )
