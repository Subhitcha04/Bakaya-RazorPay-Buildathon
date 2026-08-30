"""
Thin wrapper around Razorpay's REST API for the specific actions Bakaya
needs: payment links, refunds, fetching payment state. HTTP transport
is injectable (same pluggable pattern as every stub in this repo) so
the client logic -- auth, idempotency-key placement, retry/backoff --
is testable without live credentials or network access.

FIELD SHAPES VERIFIED against Razorpay's real API reference (not
invented): razorpay.com/docs/api/payments/payment-links/create-standard/,
.../entity/, .../fetch-id-standard/. create_payment_link's payload
shape (amount, currency, description, customer.contact, reference_id,
notify) and the response shape (id starting "plink_", short_url,
status, payments array null until a customer actually pays) both
match Razorpay's documented contract exactly.

RequestsTransport below IS the real transport -- not a sketch -- but
this sandbox still has no network egress to api.razorpay.com, so it
has never been exercised against the live API from here. Tested
against a fake transport (tests/test_razorpay_client.py) that proves
the CLIENT LOGIC is correct; scripts/smoke_test_razorpay.py is the
real create+fetch round trip meant to run on your own machine, where
real network access exists.

Test mode caps you at 30 payment links per business -- don't run the
smoke test repeatedly without a reason.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

BASE_URL = "https://api.razorpay.com/v1"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    json_body: dict[str, Any]


class HTTPTransport(Protocol):
    def post(self, url: str, auth: tuple[str, str], json: dict, timeout: float) -> HTTPResponse: ...
    def get(self, url: str, auth: tuple[str, str], timeout: float) -> HTTPResponse: ...


class RazorpayAPIError(Exception):
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Razorpay API error {status_code}: {body}")


class RazorpayClient:
    def __init__(
        self, key_id: str, key_secret: str, transport: HTTPTransport,
        base_url: str = BASE_URL, sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.key_id = key_id
        self.key_secret = key_secret
        self.transport = transport
        self.base_url = base_url
        self.sleep_fn = sleep_fn

    def _post_with_retry(self, path: str, payload: dict) -> dict:
        last_error: RazorpayAPIError | None = None
        for attempt in range(MAX_RETRIES):
            resp = self.transport.post(
                f"{self.base_url}{path}", auth=(self.key_id, self.key_secret),
                json=payload, timeout=10,
            )
            if resp.status_code < 500:
                if resp.status_code >= 400:
                    raise RazorpayAPIError(resp.status_code, resp.json_body)
                return resp.json_body
            last_error = RazorpayAPIError(resp.status_code, resp.json_body)
            if attempt < MAX_RETRIES - 1:
                self.sleep_fn(BACKOFF_BASE_SECONDS * (2 ** attempt))
        raise last_error

    def create_payment_link(
        self, amount_paise: int, description: str, customer_contact: str, reference_id: str,
    ) -> dict:
        payload = {
            "amount": amount_paise, "currency": "INR", "description": description,
            "customer": {"contact": customer_contact}, "reference_id": reference_id,
            "notify": {"sms": False, "email": False},
        }
        return self._post_with_retry("/payment_links", payload)

    def get_payment_link(self, payment_link_id: str) -> dict:
        resp = self.transport.get(
            f"{self.base_url}/payment_links/{payment_link_id}",
            auth=(self.key_id, self.key_secret), timeout=10,
        )
        if resp.status_code >= 400:
            raise RazorpayAPIError(resp.status_code, resp.json_body)
        return resp.json_body

    def create_refund(self, payment_id: str, amount_paise: int, idempotency_key: str) -> dict:
        payload = {"amount": amount_paise, "notes": {"bakaya_idempotency_key": idempotency_key}}
        return self._post_with_retry(f"/payments/{payment_id}/refund", payload)

    def fetch_payment(self, payment_id: str) -> dict:
        resp = self.transport.get(
            f"{self.base_url}/payments/{payment_id}", auth=(self.key_id, self.key_secret), timeout=10,
        )
        if resp.status_code >= 400:
            raise RazorpayAPIError(resp.status_code, resp.json_body)
        return resp.json_body


class RequestsTransport:
    def post(self, url: str, auth: tuple[str, str], json: dict, timeout: float) -> HTTPResponse:
        import requests
        r = requests.post(url, auth=auth, json=json, timeout=timeout)
        return HTTPResponse(status_code=r.status_code, json_body=r.json())

    def get(self, url: str, auth: tuple[str, str], timeout: float) -> HTTPResponse:
        import requests
        r = requests.get(url, auth=auth, timeout=timeout)
        return HTTPResponse(status_code=r.status_code, json_body=r.json())
