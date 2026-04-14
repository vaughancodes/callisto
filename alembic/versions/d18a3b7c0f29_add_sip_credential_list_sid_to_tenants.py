"""Add sip_credential_list_sid to tenants

Revision ID: d18a3b7c0f29
Revises: c4e7a92f1b48
Create Date: 2026-04-14 13:10:00.000000

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d18a3b7c0f29"
down_revision = "c4e7a92f1b48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("sip_credential_list_sid", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "sip_credential_list_sid")
