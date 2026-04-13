import uuid

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callisto.extensions import db


class Contact(db.Model):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String)
    phone_numbers: Mapped[list] = mapped_column(JSONB, default=list)
    email: Mapped[str | None] = mapped_column(String)
    google_contact_id: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[str] = mapped_column(db.DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        db.DateTime, server_default=func.now(), onupdate=func.now()
    )

    tenant = relationship("Tenant", back_populates="contacts")
    calls = relationship("Call", back_populates="contact", lazy="dynamic")
