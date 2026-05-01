"""Add voicemail_mode to phone_numbers

Revision ID: e9f4c1a2d873
Revises: a8d5e2b1c907
Create Date: 2026-04-23 16:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = "e9f4c1a2d873"
down_revision = "a8d5e2b1c907"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "phone_numbers",
        sa.Column(
            "voicemail_mode",
            sa.String(),
            nullable=False,
            server_default=sa.text("'carrier'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("phone_numbers", "voicemail_mode")
