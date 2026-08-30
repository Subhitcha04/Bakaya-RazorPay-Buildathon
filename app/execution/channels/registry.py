"""
Channel registry -- same ModuleX-adapter pattern as
control_plane/gates/base.py and detectors/base.py. Exactly ONE channel
should have is_simulated=False; tests/test_channels.py asserts this
mechanically, so a future channel addition can't silently flip that
invariant without a test failing.
"""
from __future__ import annotations

from . import email_real, whatsapp_sim, sms_sim, voice_sim

CHANNEL_MODULES = {
    "email": email_real,
    "whatsapp": whatsapp_sim,
    "sms": sms_sim,
    "voice": voice_sim,
}


def get_channel(name: str):
    if name not in CHANNEL_MODULES:
        raise ValueError(f"unknown channel: {name!r}")
    return CHANNEL_MODULES[name]
