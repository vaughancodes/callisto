import uuid

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callisto.extensions import db


class Tenant(db.Model):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    api_key_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(db.DateTime(timezone=True), server_default=func.now())

    calls = relationship("Call", back_populates="tenant", lazy="dynamic")
    contacts = relationship("Contact", back_populates="tenant", lazy="dynamic")
    insight_templates = relationship("InsightTemplate", back_populates="tenant", lazy="dynamic")
    users = relationship("User", back_populates="tenant", lazy="dynamic")
