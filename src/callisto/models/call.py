import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callisto.extensions import db


class Call(db.Model):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String, index=True)
    stream_sid: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), index=True
    )
    caller_number: Mapped[str] = mapped_column(String, nullable=False)
    callee_number: Mapped[str | None] = mapped_column(String)
    agent_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    tenant = relationship("Tenant", back_populates="calls")
    contact = relationship("Contact", back_populates="calls")
    transcripts = relationship("Transcript", back_populates="call", lazy="dynamic")
    insights = relationship("Insight", back_populates="call", lazy="dynamic")
    summary = relationship("CallSummary", back_populates="call", uselist=False)


class CallSummary(db.Model):
    __tablename__ = "call_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id"), unique=True, nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str] = mapped_column(String, nullable=False)
    key_topics: Mapped[dict] = mapped_column(JSONB, default=list)
    action_items: Mapped[dict] = mapped_column(JSONB, default=list)
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    token_cost: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call = relationship("Call", back_populates="summary")
