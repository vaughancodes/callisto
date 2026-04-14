import uuid

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callisto.extensions import db


class Tenant(db.Model):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    api_key_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Twilio SIP Domain — one per tenant, created lazily the first time a
    # SIP user is minted under this tenant.
    sip_domain_sid: Mapped[str | None] = mapped_column(String)
    sip_domain_name: Mapped[str | None] = mapped_column(String)
    sip_credential_list_sid: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(db.DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="tenants")
    calls = relationship("Call", back_populates="tenant", lazy="dynamic")
    contacts = relationship("Contact", back_populates="tenant", lazy="dynamic")
    insight_templates = relationship("InsightTemplate", back_populates="tenant", lazy="dynamic")
    users = relationship("User", back_populates="tenant", lazy="dynamic")
    memberships = relationship(
        "TenantMembership", back_populates="tenant", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    phone_numbers = relationship(
        "PhoneNumber", back_populates="tenant", lazy="dynamic",
    )
