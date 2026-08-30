from __future__ import annotations

from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchant"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    spend_cap_paise_daily: Mapped[int] = mapped_column(Integer, default=0)
    razorpay_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Customer(Base, TimestampMixin):
    __tablename__ = "customer"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant.id"), index=True)
    contact_hash: Mapped[str] = mapped_column(String(128), default="")  # hashed, never raw PII at rest
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    ltv_band: Mapped[str] = mapped_column(String(16), default="unknown")  # low/mid/high/unknown


class Consent(Base, TimestampMixin):
    __tablename__ = "consent"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customer.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32))  # email/sms/whatsapp/voice
    state: Mapped[str] = mapped_column(String(16))    # granted/revoked
    source: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (
        UniqueConstraint("customer_id", "channel", name="uq_consent_customer_channel"),
    )


class Suppression(Base, TimestampMixin):
    """
    Permanent opt-out. Enforced as a DB constraint, not a flag some code
    path could forget to check. See COMPLIANCE.md: "no exceptions"
    implemented as a UNIQUE row, not a prayer.
    """
    __tablename__ = "suppression"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customer.id"), index=True)
    reason: Mapped[str] = mapped_column(String(255), default="")

    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_suppression_customer"),
    )
