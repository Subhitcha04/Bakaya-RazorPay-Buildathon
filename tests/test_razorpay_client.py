from dataclasses import dataclass, field

from app.execution.razorpay_client import RazorpayClient, RazorpayAPIError, HTTPResponse


@dataclass
class FakeTransport:
    responses: list[HTTPResponse]
    calls: list[dict] = field(default_factory=list)
    _idx: int = 0

    def post(self, url, auth, json, timeout):
        self.calls.append({"method": "POST", "url": url, "auth": auth, "json": json, "timeout": timeout})
        resp = self.responses[self._idx]
        self._idx += 1
        return resp

    def get(self, url, auth, timeout):
        self.calls.append({"method": "GET", "url": url, "auth": auth, "timeout": timeout})
        resp = self.responses[self._idx]
        self._idx += 1
        return resp


def _client(transport, sleep_calls=None):
    sleep_fn = (lambda s: sleep_calls.append(s)) if sleep_calls is not None else (lambda s: None)
    return RazorpayClient(key_id="rzp_test_key", key_secret="rzp_test_secret",
                           transport=transport, sleep_fn=sleep_fn)


def test_create_payment_link_sends_correct_auth_and_payload():
    transport = FakeTransport(responses=[HTTPResponse(200, {"id": "plink_1", "short_url": "https://x"})])
    client = _client(transport)

    result = client.create_payment_link(
        amount_paise=49900, description="Recovery", customer_contact="+919999999999",
        reference_id="idem_key_abc",
    )

    assert result["id"] == "plink_1"
    call = transport.calls[0]
    assert call["auth"] == ("rzp_test_key", "rzp_test_secret")
    assert call["json"]["amount"] == 49900
    assert call["json"]["reference_id"] == "idem_key_abc"
    assert call["url"].endswith("/payment_links")


def test_4xx_fails_immediately_without_retry():
    transport = FakeTransport(responses=[HTTPResponse(400, {"error": "bad request"})])
    client = _client(transport)

    try:
        client.create_payment_link(1000, "x", "+91123", "idem_1")
        assert False, "expected RazorpayAPIError"
    except RazorpayAPIError as e:
        assert e.status_code == 400
    assert len(transport.calls) == 1


def test_5xx_retries_with_backoff_then_succeeds():
    transport = FakeTransport(responses=[
        HTTPResponse(500, {"error": "server error"}),
        HTTPResponse(200, {"id": "plink_2"}),
    ])
    sleep_calls = []
    client = _client(transport, sleep_calls=sleep_calls)

    result = client.create_payment_link(1000, "x", "+91123", "idem_2")
    assert result["id"] == "plink_2"
    assert len(transport.calls) == 2
    assert len(sleep_calls) == 1


def test_5xx_exhausts_retries_and_raises():
    transport = FakeTransport(responses=[
        HTTPResponse(500, {"error": "1"}),
        HTTPResponse(500, {"error": "2"}),
        HTTPResponse(500, {"error": "3"}),
    ])
    sleep_calls = []
    client = _client(transport, sleep_calls=sleep_calls)

    try:
        client.create_payment_link(1000, "x", "+91123", "idem_3")
        assert False, "expected RazorpayAPIError after exhausting retries"
    except RazorpayAPIError as e:
        assert e.status_code == 500
    assert len(transport.calls) == 3


def test_create_refund_carries_idempotency_key_in_notes():
    transport = FakeTransport(responses=[HTTPResponse(200, {"id": "rfnd_1"})])
    client = _client(transport)

    client.create_refund(payment_id="pay_1", amount_paise=5000, idempotency_key="idem_refund_1")
    call = transport.calls[0]
    assert call["json"]["notes"]["bakaya_idempotency_key"] == "idem_refund_1"
    assert call["url"].endswith("/payments/pay_1/refund")


def test_fetch_payment_returns_parsed_body_on_success():
    transport = FakeTransport(responses=[HTTPResponse(200, {"id": "pay_1", "status": "captured"})])
    client = _client(transport)

    result = client.fetch_payment("pay_1")
    assert result["status"] == "captured"
    assert transport.calls[0]["method"] == "GET"


def test_fetch_payment_raises_on_error_status():
    transport = FakeTransport(responses=[HTTPResponse(404, {"error": "not found"})])
    client = _client(transport)

    try:
        client.fetch_payment("nonexistent")
        assert False, "expected RazorpayAPIError"
    except RazorpayAPIError as e:
        assert e.status_code == 404


def test_get_payment_link_returns_parsed_body_on_success():
    transport = FakeTransport(responses=[HTTPResponse(200, {
        "id": "plink_abc123", "short_url": "https://rzp.io/i/xyz",
        "status": "created", "reference_id": "case_1", "payments": None,
    })])
    client = _client(transport)

    result = client.get_payment_link("plink_abc123")
    assert result["id"] == "plink_abc123"
    assert result["status"] == "created"
    assert result["payments"] is None

    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"].endswith("/payment_links/plink_abc123")
    assert call["auth"] == ("rzp_test_key", "rzp_test_secret")


def test_get_payment_link_raises_on_error_status():
    transport = FakeTransport(responses=[HTTPResponse(404, {"error": {"description": "no such link"}})])
    client = _client(transport)

    try:
        client.get_payment_link("plink_nonexistent")
        assert False, "expected RazorpayAPIError"
    except RazorpayAPIError as e:
        assert e.status_code == 404
