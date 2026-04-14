"""Organization-admin endpoints.

These let an organization admin manage their own org: edit name/description,
manage org admins, manage the number pool (assigning numbers from the pool
to specific tenants), and create/delete tenants within the org.
"""

import hashlib
import logging
import re
import secrets

from flask import jsonify, request

from callisto import twilio_client
from callisto.api import bp
from callisto.auth.middleware import require_org_admin
from callisto.extensions import db
from callisto.models import (
    Organization,
    OrganizationMembership,
    PhoneNumber,
    Tenant,
    User,
)


def revoke_sip_user(pn: PhoneNumber) -> None:
    """Delete the Twilio SIP credential attached to this PhoneNumber and
    clear the local columns. Safe to call when no SIP user is configured
    (no-op). Errors from Twilio are logged but don't block the caller."""
    if not pn.sip_credential_sid:
        return
    tenant = Tenant.query.filter_by(id=pn.tenant_id).first() if pn.tenant_id else None
    list_sid = tenant.sip_credential_list_sid if tenant else None
    if list_sid:
        try:
            twilio_client.delete_sip_credential(
                list_sid=list_sid, credential_sid=pn.sip_credential_sid
            )
        except twilio_client.TwilioClientError as exc:
            logger.warning(
                "Failed to revoke SIP credential %s on %s: %s",
                pn.sip_credential_sid, pn.e164, exc,
            )
    pn.sip_username = None
    pn.sip_credential_sid = None

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s or "tenant"


def _serialize_organization(o: Organization) -> dict:
    return {
        "id": str(o.id),
        "name": o.name,
        "slug": o.slug,
        "description": o.description,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _serialize_tenant_brief(t: Tenant) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "description": t.description,
    }


def _serialize_phone_number(p: PhoneNumber) -> dict:
    return {
        "id": str(p.id),
        "organization_id": str(p.organization_id),
        "tenant_id": str(p.tenant_id) if p.tenant_id else None,
        "e164": p.e164,
        "twilio_sid": p.twilio_sid,
        "friendly_name": p.friendly_name,
        "inbound_enabled": p.inbound_enabled,
        "outbound_enabled": p.outbound_enabled,
    }


# --- Organization details ---

@bp.route("/organizations/<uuid:org_id>", methods=["GET"])
def get_organization(org_id):
    require_org_admin(org_id)
    org = db.get_or_404(Organization, org_id)
    return jsonify(_serialize_organization(org))


@bp.route("/organizations/<uuid:org_id>", methods=["PUT"])
def update_organization(org_id):
    require_org_admin(org_id)
    org = db.get_or_404(Organization, org_id)
    data = request.get_json() or {}

    # Org admins can edit description but not name (name is managed by a
    # superadmin).
    if "description" in data:
        org.description = data["description"]

    db.session.commit()
    return jsonify(_serialize_organization(org))


# --- Tenants in this org ---

@bp.route("/organizations/<uuid:org_id>/tenants", methods=["GET"])
def list_organization_tenants(org_id):
    require_org_admin(org_id)
    db.get_or_404(Organization, org_id)
    tenants = (
        Tenant.query.filter_by(organization_id=str(org_id))
        .order_by(Tenant.name)
        .all()
    )
    return jsonify([_serialize_tenant_brief(t) for t in tenants])


@bp.route(
    "/organizations/<uuid:org_id>/tenants/<uuid:tenant_id>", methods=["PUT"]
)
def update_organization_tenant(org_id, tenant_id):
    require_org_admin(org_id)
    tenant = db.get_or_404(Tenant, tenant_id)
    if str(tenant.organization_id) != str(org_id):
        return jsonify({"error": "Tenant not found in this organization"}), 404
    data = request.get_json() or {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        if name != tenant.name:
            tenant.name = name
            # Slug auto-tracks the name. Find a unique form by appending
            # -2, -3, ... if the bare slug collides with another tenant.
            base_slug = _slugify(name)
            new_slug = base_slug
            suffix = 2
            while True:
                collision = (
                    Tenant.query.filter(Tenant.slug == new_slug)
                    .filter(Tenant.id != tenant.id)
                    .first()
                )
                if not collision:
                    break
                new_slug = f"{base_slug}-{suffix}"
                suffix += 1
            tenant.slug = new_slug
    if "description" in data:
        tenant.description = data["description"] or None
    db.session.commit()
    return jsonify(_serialize_tenant_brief(tenant))


@bp.route(
    "/organizations/<uuid:org_id>/tenants/<uuid:tenant_id>", methods=["DELETE"]
)
def delete_organization_tenant(org_id, tenant_id):
    require_org_admin(org_id)
    from callisto.api.admin import cascade_delete_tenant

    tenant = db.get_or_404(Tenant, tenant_id)
    if str(tenant.organization_id) != str(org_id):
        return jsonify({"error": "Tenant not found in this organization"}), 404
    cascade_delete_tenant(tenant)
    db.session.commit()
    return "", 204


@bp.route("/organizations/<uuid:org_id>/tenants", methods=["POST"])
def create_organization_tenant(org_id):
    require_org_admin(org_id)
    org = db.get_or_404(Organization, org_id)
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    base_slug = _slugify(data.get("slug") or name)
    slug = base_slug
    suffix = 2
    while Tenant.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    api_key = secrets.token_urlsafe(32)
    tenant = Tenant(
        organization_id=org.id,
        name=name,
        slug=slug,
        description=data.get("description"),
        api_key_hash=hashlib.sha256(api_key.encode()).hexdigest(),
    )
    db.session.add(tenant)
    db.session.commit()
    return jsonify(_serialize_tenant_brief(tenant)), 201


# --- Number pool (org admin) ---

@bp.route("/organizations/<uuid:org_id>/numbers", methods=["GET"])
def list_org_numbers(org_id):
    require_org_admin(org_id)
    db.get_or_404(Organization, org_id)
    numbers = (
        PhoneNumber.query.filter_by(organization_id=str(org_id))
        .order_by(PhoneNumber.e164)
        .all()
    )
    return jsonify([_serialize_phone_number(p) for p in numbers])


@bp.route(
    "/organizations/<uuid:org_id>/numbers/<uuid:number_id>", methods=["PUT"]
)
def update_org_number(org_id, number_id):
    """Assign a number to (or unassign from) a tenant within this org.

    Body: { "tenant_id": "<uuid>" | null }
    """
    require_org_admin(org_id)
    pn = db.get_or_404(PhoneNumber, number_id)
    if str(pn.organization_id) != str(org_id):
        return jsonify({"error": "Number does not belong to this organization"}), 404

    data = request.get_json() or {}
    if "tenant_id" not in data:
        return jsonify({"error": "tenant_id is required"}), 400

    new_tenant_id = data["tenant_id"]
    same_tenant = (
        new_tenant_id is not None
        and pn.tenant_id is not None
        and str(pn.tenant_id) == str(new_tenant_id)
    )

    if not same_tenant:
        # Any tenant change (assign/unassign/reassign) revokes the SIP
        # credential — it was minted against the previous tenant's SIP
        # Domain and would no longer be valid.
        revoke_sip_user(pn)

    if new_tenant_id is None:
        pn.tenant_id = None
        pn.inbound_enabled = False
        pn.outbound_enabled = False
        pn.inbound_mode = "none"
        pn.inbound_forward_to = None
    else:
        tenant = Tenant.query.filter_by(id=new_tenant_id).first()
        if not tenant or str(tenant.organization_id) != str(org_id):
            return jsonify({
                "error": "Tenant not found in this organization",
            }), 404
        if not same_tenant:
            pn.tenant_id = tenant.id
            # Newly-assigned numbers start with no routing — the tenant
            # admin explicitly opts in to inbound/outbound from Tenant
            # Settings.
            pn.inbound_enabled = False
            pn.outbound_enabled = False
            pn.inbound_mode = "none"
            pn.inbound_forward_to = None

    db.session.commit()
    return jsonify(_serialize_phone_number(pn))


# --- Org admins ---

@bp.route("/organizations/<uuid:org_id>/admins", methods=["GET"])
def list_org_admins(org_id):
    require_org_admin(org_id)
    db.get_or_404(Organization, org_id)
    rows = (
        OrganizationMembership.query.filter_by(organization_id=str(org_id))
        .join(User, OrganizationMembership.user_id == User.id)
        .order_by(User.name)
        .all()
    )
    return jsonify([
        {
            "user_id": str(m.user_id),
            "email": m.user.email,
            "name": m.user.name,
            "is_admin": m.is_admin,
        }
        for m in rows
    ])


@bp.route("/organizations/<uuid:org_id>/admins", methods=["POST"])
def add_org_admin(org_id):
    require_org_admin(org_id)
    db.get_or_404(Organization, org_id)
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            "error": "No user with that email exists. They must sign in at least once first.",
        }), 404

    existing = OrganizationMembership.query.filter_by(
        user_id=user.id, organization_id=str(org_id)
    ).first()
    if existing:
        existing.is_admin = True
    else:
        existing = OrganizationMembership(
            user_id=user.id, organization_id=str(org_id), is_admin=True
        )
        db.session.add(existing)
    db.session.commit()

    return jsonify({
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "is_admin": True,
    }), 201


@bp.route(
    "/organizations/<uuid:org_id>/admins/<uuid:user_id>", methods=["DELETE"]
)
def remove_org_admin(org_id, user_id):
    require_org_admin(org_id)
    membership = OrganizationMembership.query.filter_by(
        organization_id=str(org_id), user_id=str(user_id)
    ).first_or_404()
    db.session.delete(membership)
    db.session.commit()
    return "", 204
