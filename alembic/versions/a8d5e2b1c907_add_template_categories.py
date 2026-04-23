"""Add template_categories table and seed from existing template categories

Revision ID: a8d5e2b1c907
Revises: f3a7b2e9c104
Create Date: 2026-04-20 11:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = "a8d5e2b1c907"
down_revision = "f3a7b2e9c104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_categories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_template_category_tenant_name"
        ),
    )
    op.create_index(
        "ix_template_categories_tenant_id",
        "template_categories",
        ["tenant_id"],
    )

    # Seed: for every distinct (tenant_id, category) pair in insight_templates,
    # create a matching template_categories row so existing templates keep
    # their category value valid under the new per-tenant list.
    op.execute(
        """
        INSERT INTO template_categories (id, tenant_id, name)
        SELECT gen_random_uuid(), tenant_id, category
        FROM (
            SELECT DISTINCT tenant_id, category
            FROM insight_templates
            WHERE category IS NOT NULL AND category <> ''
        ) AS distinct_cats
        ON CONFLICT (tenant_id, name) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_template_categories_tenant_id", table_name="template_categories")
    op.drop_table("template_categories")
