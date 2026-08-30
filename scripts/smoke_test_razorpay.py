"""
The FIRST real, live call this project has ever made to Razorpay.
Everything else (RazorpayClient's auth/retry/idempotency logic) has
only ever been tested against a fake transport, because the sandbox
this project was built in has no network route to api.razorpay.com.
This script runs on YOUR machine, which does.

Does a real create+fetch round trip using RazorpayClient exactly as
the rest of the codebase would call it -- no shortcuts, no mocking.
Costs nothing (test mode, no real money) but DOES count against the
30-payment-links-per-business test-mode cap, so don't run this in a
loop.

Requires:
  pip install requests
  RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET set (in your environment or a
  loaded .env file) -- test-mode keys, starting rzp_test_
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, ".")

from app.execution.razorpay_client import RazorpayClient, RazorpayAPIError, RequestsTransport


def main() -> int:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        print("ERROR: RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must both be set.")
        print("Load them from your .env file first, or export them directly.")
        return 1

    if not key_id.startswith("rzp_test_"):
        print(f"WARNING: key_id {key_id!r} doesn't start with 'rzp_test_' -- "
              f"are you sure this is a test-mode key? Refusing to proceed with a live-mode key.")
        return 1

    try:
        import requests  # noqa: F401
    except ImportError:
        print("ERROR: the `requests` package is required. Install it with: pip install requests")
        return 1

    client = RazorpayClient(key_id=key_id, key_secret=key_secret, transport=RequestsTransport())

    reference_id = f"bakaya_smoke_{int(time.time())}"
    print(f"Creating a real test-mode payment link (reference_id={reference_id})...")

    try:
        link = client.create_payment_link(
            amount_paise=100,
            description="Bakaya smoke test -- safe to ignore/expire",
            customer_contact="+919876543210",
            reference_id=reference_id,
        )
    except RazorpayAPIError as e:
        print(f"\nFAILED to create payment link: {e}")
        print("Common causes: wrong key_id/key_secret, or not actually in test mode.")
        return 1

    print("\nSUCCESS -- real response from Razorpay:")
    print(f"  id:         {link['id']}")
    print(f"  short_url:  {link['short_url']}")
    print(f"  status:     {link['status']}")
    print(f"  reference_id: {link['reference_id']}")

    print(f"\nFetching it back via GET /payment_links/{link['id']}...")
    try:
        fetched = client.get_payment_link(link["id"])
    except RazorpayAPIError as e:
        print(f"\nFAILED to fetch payment link back: {e}")
        return 1

    print("SUCCESS -- fetched back:")
    print(f"  id matches:            {fetched['id'] == link['id']}")
    print(f"  reference_id matches:  {fetched['reference_id'] == reference_id}")
    print(f"  status:                {fetched['status']}")
    print(f"  payments (null until someone actually pays): {fetched['payments']}")

    print(f"\nReal create+fetch round trip confirmed against live Razorpay test mode.")
    print(f"Link (safe to open, no real money): {link['short_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
