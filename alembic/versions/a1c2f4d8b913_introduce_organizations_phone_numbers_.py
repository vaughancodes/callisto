"""Introduce organizations, phone_numbers, and template direction flags

Revision ID: a1c2f4d8b913
Revises: 759e11cbc109
Create Date: 2026-04-14 12:00:00.000000

"""
import re
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a1c2f4d8b913"
down_revision = "759e11cbc109"
branch_labels = None
depends_on = None


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "org"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create new tables
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index(
        "ix_organizations_slug", "organizations", ["slug"], unique=True
    )

    op.create_table(
        "organization_memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "organization_id", name="uq_user_organization"
        ),
    )
    op.create_index(
        "ix_organization_memberships_user_id",
        "organization_memberships",
        ["user_id"],
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
    )

    op.create_table(
        "phone_numbers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=True,
        ),
        sa.Column("e164", sa.String(), nullable=False),
        sa.Column("twilio_sid", sa.String()),
        sa.Column("friendly_name", sa.String()),
        sa.Column(
            "inbound_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "outbound_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("e164", name="uq_phone_number_e164"),
    )
    op.create_index(
        "ix_phone_numbers_organization_id",
        "phone_numbers",
        ["organization_id"],
    )
    op.create_index(
        "ix_phone_numbers_tenant_id", "phone_numbers", ["tenant_id"]
    )
    op.create_index(
        "ix_phone_numbers_twilio_sid", "phone_numbers", ["twilio_sid"]
    )

    # ------------------------------------------------------------------
    # 2. Add organization_id to tenants (nullable for backfill)
    # ------------------------------------------------------------------
    op.add_column(
        "tenants",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tenants_organization_id", "tenants", ["organization_id"]
    )

    # ------------------------------------------------------------------
    # 3. Insight template direction flags
    # ------------------------------------------------------------------
    op.add_column(
        "insight_templates",
        sa.Column(
            "inbound_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "insight_templates",
        sa.Column(
            "outbound_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # ------------------------------------------------------------------
    # 4. Data migration: wrap each tenant in its own organization,
    #    promote tenant admins to org admins, and move twilio_numbers
    #    out of tenant.settings into the phone_numbers table.
    # ------------------------------------------------------------------
    bind = op.get_bind()

    tenants = bind.execute(
        sa.text("SELECT id, name, slug, settings FROM tenants")
    ).fetchall()

    used_slugs: set[str] = set(
        row[0]
        for row in bind.execute(sa.text("SELECT slug FROM organizations")).fetchall()
    )

    for tenant_row in tenants:
        tenant_id = tenant_row[0]
        tenant_name = tenant_row[1]
        tenant_slug = tenant_row[2]
        settings = tenant_row[3] or {}

        org_id = uuid.uuid4()
        base_slug = _slugify(f"{tenant_slug}-org")
        slug = base_slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used_slugs.add(slug)

        bind.execute(
            sa.text(
                "INSERT INTO organizations (id, name, slug) "
                "VALUES (:id, :name, :slug)"
            ),
            {"id": org_id, "name": tenant_name, "slug": slug},
        )
        bind.execute(
            sa.text(
                "UPDATE tenants SET organization_id = :org_id WHERE id = :tid"
            ),
            {"org_id": org_id, "tid": tenant_id},
        )

        # Promote every existing tenant admin to org admin
        admins = bind.execute(
            sa.text(
                "SELECT user_id FROM tenant_memberships "
                "WHERE tenant_id = :tid AND is_admin = true"
            ),
            {"tid": tenant_id},
        ).fetchall()
        for (user_id,) in admins:
            bind.execute(
                sa.text(
                    "INSERT INTO organization_memberships "
                    "(user_id, organization_id, is_admin) "
                    "VALUES (:uid, :oid, true) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"uid": user_id, "oid": org_id},
            )

        # Move tenant.settings.twilio_numbers -> phone_numbers rows
        for raw in settings.get("twilio_numbers", []) or []:
            if not raw:
                continue
            e164 = raw.strip()
            try:
                bind.execute(
                    sa.text(
                        "INSERT INTO phone_numbers "
                        "(organization_id, tenant_id, e164, "
                        "inbound_enabled, outbound_enabled) "
                        "VALUES (:oid, :tid, :e164, true, false)"
                    ),
                    {"oid": org_id, "tid": tenant_id, "e164": e164},
                )
            except sa.exc.IntegrityError:
                # Number was already migrated under a different tenant;
                # skip the duplicate. Safe because of the uq_phone_number_e164.
                pass

    # ------------------------------------------------------------------
    # 5. Lock organization_id NOT NULL now that backfill is done
    # ------------------------------------------------------------------
    op.alter_column("tenants", "organization_id", nullable=False)


def downgrade() -> None:
    op.drop_column("insight_templates", "outbound_enabled")
    op.drop_column("insight_templates", "inbound_enabled")

    op.drop_index("ix_tenants_organization_id", table_name="tenants")
    op.drop_column("tenants", "organization_id")

    op.drop_index("ix_phone_numbers_twilio_sid", table_name="phone_numbers")
    op.drop_index("ix_phone_numbers_tenant_id", table_name="phone_numbers")
    op.drop_index(
        "ix_phone_numbers_organization_id", table_name="phone_numbers"
    )
    op.drop_table("phone_numbers")

    op.drop_index(
        "ix_organization_memberships_organization_id",
        table_name="organization_memberships",
    )
    op.drop_index(
        "ix_organization_memberships_user_id",
        table_name="organization_memberships",
    )
    op.drop_table("organization_memberships")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
