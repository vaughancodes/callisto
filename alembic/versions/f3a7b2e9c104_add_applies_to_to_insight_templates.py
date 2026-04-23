"""Add applies_to to insight_templates

Revision ID: f3a7b2e9c104
Revises: d18a3b7c0f29
Create Date: 2026-04-20 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = "f3a7b2e9c104"
down_revision = "d18a3b7c0f29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "insight_templates",
        sa.Column(
            "applies_to",
            sa.String(),
            nullable=False,
            server_default="both",
        ),
    )


def downgrade() -> None:
    op.drop_column("insight_templates", "applies_to")
