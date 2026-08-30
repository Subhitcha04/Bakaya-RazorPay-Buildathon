"""
Every channel implements the same interface: send(recipient, subject,
body, idempotency_key) -> ChannelSendResult. Declared vs real is a
property of the IMPLEMENTATION, not the interface -- see the README's
"what is real vs simulated" table. Only email_real.py genuinely
dispatches over a real protocol (SMTP); the rest log what WOULD have
been sent and return a result shaped identically, so nothing downstream
needs to know or care which kind of channel it's talking to.

is_simulated is a FIELD on the result, not just a docstring claim --
that's deliberate. It means the honesty of the README table is
mechanically checkable (see channels/registry.py's test asserting
exactly one channel has is_simulated=False) rather than something a
human has to remember to keep accurate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ChannelSendResult:
    sent: bool
    channel: str
    idempotency_key: str
    provider_message_id: str | None
    is_simulated: bool
    raw_response: dict[str, Any]


class ChannelAdapter(Protocol):
    channel_name: str
    is_simulated: bool
    def send(self, recipient: str, subject: str, body: str, idempotency_key: str) -> ChannelSendResult: ...
