from __future__ import annotations

import os


class Settings:
    """
    Loaded from environment / secrets manager. Never commit real values --
    see .env.example. A CI check should grep for key-shaped strings in
    every commit (see SECURITY.md).
    """
    def __init__(self) -> None:
        self.razorpay_webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        self.razorpay_key_id = os.getenv("RAZORPAY_KEY_ID", "")
        self.razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")


settings = Settings()
