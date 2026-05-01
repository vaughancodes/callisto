import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callisto.extensions import db


class PhoneNumber(db.Model):
    """A Twilio phone number owned by an organization.

    Lives in the org pool until assigned to a specific tenant. Once assigned,
    the tenant admin can toggle whether it can be used for inbound and/or
    outbound calls.
    """

    __tablename__ = "phone_numbers"
    __table_args__ = (
        UniqueConstraint("e164", name="uq_phone_number_e164"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        index=True,
        nullable=True,
    )
    e164: Mapped[str] = mapped_column(String, nullable=False)
    twilio_sid: Mapped[str | None] = mapped_column(String, index=True)
    friendly_name: Mapped[str | None] = mapped_column(String)
    inbound_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    outbound_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Optional SIP user assigned to this number. When present, the agent's
    # SIP device (deskphone or softphone) registers with these creds and
    # outbound calls flow through Twilio with this number as the From.
    sip_username: Mapped[str | None] = mapped_column(String)
    sip_credential_sid: Mapped[str | None] = mapped_column(String)
    # Per-number inbound routing: 'none' (record-only), 'sip' (ring the
    # registered SIP device), or 'forward' (dial inbound_forward_to).
    inbound_mode: Mapped[str] = mapped_column(
        String, nullable=False, server_default="none"
    )
    inbound_forward_to: Mapped[str | None] = mapped_column(String)
    # What happens when an inbound call isn't answered: "carrier" lets the
    # destination (desk phone / forwarded carrier) handle voicemail, "app"
    # makes Callisto catch it with a shorter Dial timeout so we beat the
    # carrier's own voicemail pickup.
    voicemail_mode: Mapped[str] = mapped_column(
        String, nullable=False, server_default="carrier"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    organization = relationship("Organization", back_populates="phone_numbers")
    tenant = relationship("Tenant", back_populates="phone_numbers")
