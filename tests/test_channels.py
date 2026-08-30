import smtplib

import pytest

from app.execution.channels import email_real, whatsapp_sim, sms_sim, voice_sim
from app.execution.channels.registry import CHANNEL_MODULES, get_channel


class FakeSMTP:
    def __init__(self):
        self.sent = []
        self.quit_called = False

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent.append({"from": from_addr, "to": to_addrs, "msg": msg})

    def quit(self):
        self.quit_called = True


class FailingSMTP(FakeSMTP):
    def sendmail(self, from_addr, to_addrs, msg):
        raise smtplib.SMTPException("connection refused")


def test_email_is_the_only_non_simulated_channel():
    real_channels = [name for name, mod in CHANNEL_MODULES.items() if not mod.is_simulated]
    assert real_channels == ["email"]


def test_email_send_genuinely_dispatches_via_smtp():
    fake = FakeSMTP()
    result = email_real.send(
        recipient="customer@example.com", subject="Payment reminder",
        body="Please complete your payment. Contact us at support@merchant.test.",
        idempotency_key="idem_1", connection_factory=lambda: fake,
    )
    assert result.sent is True
    assert result.is_simulated is False
    assert len(fake.sent) == 1
    assert fake.sent[0]["to"] == ["customer@example.com"]
    assert fake.quit_called is True


def test_email_send_propagates_smtp_failures_rather_than_swallowing_them():
    fake = FailingSMTP()
    with pytest.raises(smtplib.SMTPException):
        email_real.send(
            recipient="customer@example.com", subject="x", body="y",
            idempotency_key="idem_2", connection_factory=lambda: fake,
        )


def test_all_simulator_channels_return_is_simulated_true():
    for mod in (whatsapp_sim, sms_sim, voice_sim):
        result = mod.send(recipient="cust", subject="s", body="b", idempotency_key="idem_x")
        assert result.is_simulated is True
        assert result.sent is True


def test_all_channels_share_the_same_result_shape():
    fake_smtp = FakeSMTP()
    results = [
        email_real.send("c", "s", "b", "idem", connection_factory=lambda: fake_smtp),
        whatsapp_sim.send("c", "s", "b", "idem"),
        sms_sim.send("c", "s", "b", "idem"),
        voice_sim.send("c", "s", "b", "idem"),
    ]
    for r in results:
        assert hasattr(r, "sent") and hasattr(r, "is_simulated") and hasattr(r, "provider_message_id")


def test_registry_get_channel_returns_the_right_module():
    assert get_channel("email") is email_real
    assert get_channel("whatsapp") is whatsapp_sim


def test_registry_raises_on_unknown_channel():
    with pytest.raises(ValueError):
        get_channel("carrier_pigeon")
