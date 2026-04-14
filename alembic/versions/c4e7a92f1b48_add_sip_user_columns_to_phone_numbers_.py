"""Add SIP user columns to phone_numbers and SIP domain columns to tenants

Revision ID: c4e7a92f1b48
Revises: a1c2f4d8b913
Create Date: 2026-04-14 13:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c4e7a92f1b48"
down_revision = "a1c2f4d8b913"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tenant gets one SIP Domain (created lazily on first credential mint)
    op.add_column(
        "tenants",
        sa.Column("sip_domain_sid", sa.String(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("sip_domain_name", sa.String(), nullable=True),
    )

    # PhoneNumber: optional SIP user (one per number) + per-number inbound routing
    op.add_column(
        "phone_numbers",
        sa.Column("sip_username", sa.String(), nullable=True),
    )
    op.add_column(
        "phone_numbers",
        sa.Column("sip_credential_sid", sa.String(), nullable=True),
    )
    op.add_column(
        "phone_numbers",
        sa.Column(
            "inbound_mode",
            sa.String(),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
    )
    op.add_column(
        "phone_numbers",
        sa.Column("inbound_forward_to", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("phone_numbers", "inbound_forward_to")
    op.drop_column("phone_numbers", "inbound_mode")
    op.drop_column("phone_numbers", "sip_credential_sid")
    op.drop_column("phone_numbers", "sip_username")
    op.drop_column("tenants", "sip_domain_name")
    op.drop_column("tenants", "sip_domain_sid")
