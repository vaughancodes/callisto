"""Superadmin API endpoints for managing organizations, tenants, and users."""

import hashlib
import logging
import re
import secrets

from flask import Blueprint, jsonify, request

from callisto.auth.middleware import require_superadmin
from callisto.extensions import db
from callisto.models import (
    Organization,
    OrganizationMembership,
    PhoneNumber,
    Tenant,
)
from callisto.models.user import User
from callisto import twilio_client

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
def check_superadmin():
    require_superadmin()


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s or "org"


def _serialize_organization(o: Organization) -> dict:
    return {
        "id": str(o.id),
        "name": o.name,
        "slug": o.slug,
        "description": o.description,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "tenant_count": o.tenants.count(),
        "phone_number_count": o.phone_numbers.count(),
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


# --- Organizations ---

@admin_bp.route("/organizations", methods=["GET"])
def list_organizations():
    orgs = Organization.query.order_by(Organization.created_at.desc()).all()
    return jsonify([_serialize_organization(o) for o in orgs])


@admin_bp.route("/organizations", methods=["POST"])
def create_organization():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    base_slug = _slugify(data.get("slug") or name)
    slug = base_slug
    suffix = 2
    while Organization.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    org = Organization(
        name=name,
        slug=slug,
        description=data.get("description"),
    )
    db.session.add(org)
    db.session.commit()
    return jsonify(_serialize_organization(org)), 201


@admin_bp.route("/organizations/<uuid:org_id>", methods=["PUT"])
def update_organization(org_id):
    org = db.get_or_404(Organization, org_id)
    data = request.get_json() or {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        if name != org.name:
            org.name = name
            # Slug auto-tracks the name. Find a unique form by appending
            # -2, -3, ... if the bare slug collides with another org.
            base_slug = _slugify(name)
            new_slug = base_slug
            suffix = 2
            while True:
                collision = (
                    Organization.query.filter(Organization.slug == new_slug)
                    .filter(Organization.id != org.id)
                    .first()
                )
                if not collision:
                    break
                new_slug = f"{base_slug}-{suffix}"
                suffix += 1
            org.slug = new_slug
    if "description" in data:
        org.description = data["description"]

    db.session.commit()
    return jsonify(_serialize_organization(org))


@admin_bp.route("/organizations/<uuid:org_id>", methods=["DELETE"])
def delete_organization(org_id):
    org = db.get_or_404(Organization, org_id)
    if org.tenants.count() > 0:
        return jsonify({
            "error": "Organization still has tenants. Delete or move them first.",
        }), 409
    # Clear voice webhooks on any owned numbers before deleting them
    for pn in org.phone_numbers.all():
        if pn.twilio_sid:
            try:
                twilio_client.clear_number_voice_webhook(pn.twilio_sid)
            except twilio_client.TwilioClientError as exc:
                logger.warning("Failed to clear webhook for %s: %s", pn.e164, exc)
    db.session.delete(org)
    db.session.commit()
    return "", 204


# --- Number pool (superadmin) ---

@admin_bp.route("/twilio/numbers", methods=["GET"])
def list_twilio_numbers():
    """List every IncomingPhoneNumber on the Twilio account, joined against
    our phone_numbers table so the UI can show which org (if any) owns each.
    """
    try:
        twilio_numbers = twilio_client.list_numbers()
    except twilio_client.TwilioClientError as exc:
        return jsonify({"error": str(exc)}), 502

    sid_to_pn: dict[str, PhoneNumber] = {
        pn.twilio_sid: pn
        for pn in PhoneNumber.query.filter(PhoneNumber.twilio_sid.isnot(None)).all()
        if pn.twilio_sid
    }
    e164_to_pn: dict[str, PhoneNumber] = {
        pn.e164: pn
        for pn in PhoneNumber.query.filter(PhoneNumber.twilio_sid.is_(None)).all()
    }

    result = []
    for tn in twilio_numbers:
        pn = sid_to_pn.get(tn.sid) or e164_to_pn.get(tn.e164)
        org_name = None
        if pn:
            org = db.session.get(Organization, pn.organization_id)
            org_name = org.name if org else None
        result.append({
            "sid": tn.sid,
            "e164": tn.e164,
            "friendly_name": tn.friendly_name,
            "voice_url": tn.voice_url,
            "phone_number_id": str(pn.id) if pn else None,
            "organization_id": str(pn.organization_id) if pn else None,
            "organization_name": org_name,
            "tenant_id": str(pn.tenant_id) if (pn and pn.tenant_id) else None,
        })
    return jsonify(result)


@admin_bp.route("/organizations/<uuid:org_id>/numbers", methods=["GET"])
def list_organization_numbers(org_id):
    db.get_or_404(Organization, org_id)
    numbers = (
        PhoneNumber.query.filter_by(organization_id=str(org_id))
        .order_by(PhoneNumber.created_at)
        .all()
    )
    return jsonify([_serialize_phone_number(p) for p in numbers])


@admin_bp.route("/organizations/<uuid:org_id>/numbers", methods=["POST"])
def assign_number_to_organization(org_id):
    """Assign a Twilio number (by SID) to an organization.

    If the number is not yet in our DB, this creates the row. If it already
    belongs to a different org, returns 409.
    """
    org = db.get_or_404(Organization, org_id)
    data = request.get_json() or {}
    sid = (data.get("sid") or "").strip()
    if not sid:
        return jsonify({"error": "sid is required"}), 400

    try:
        tn = next(
            (n for n in twilio_client.list_numbers() if n.sid == sid), None
        )
    except twilio_client.TwilioClientError as exc:
        return jsonify({"error": str(exc)}), 502
    if not tn:
        return jsonify({"error": "Twilio number not found"}), 404

    existing = (
        PhoneNumber.query.filter(
            (PhoneNumber.twilio_sid == sid) | (PhoneNumber.e164 == tn.e164)
        ).first()
    )
    if existing and str(existing.organization_id) != str(org_id):
        other = db.session.get(Organization, existing.organization_id)
        return jsonify({
            "error": (
                f"{tn.e164} is already assigned to organization "
                f"'{other.name if other else existing.organization_id}'."
            ),
        }), 409

    if existing:
        existing.twilio_sid = sid
        existing.friendly_name = tn.friendly_name
        pn = existing
    else:
        pn = PhoneNumber(
            organization_id=org.id,
            e164=tn.e164,
            twilio_sid=sid,
            friendly_name=tn.friendly_name,
        )
        db.session.add(pn)

    try:
        twilio_client.configure_number_for_callisto(sid)
    except twilio_client.TwilioClientError as exc:
        return jsonify({"error": str(exc)}), 502

    db.session.commit()
    return jsonify(_serialize_phone_number(pn)), 201


@admin_bp.route(
    "/organizations/<uuid:org_id>/numbers/<uuid:number_id>", methods=["DELETE"]
)
def unassign_number_from_organization(org_id, number_id):
    """Remove a number from an organization.

    Revokes any SIP credential attached to the number, clears the Twilio
    voice webhook so the number stops routing to Callisto, then deletes
    our phone_numbers row.
    """
    from callisto.api.organizations import revoke_sip_user

    pn = db.get_or_404(PhoneNumber, number_id)
    if str(pn.organization_id) != str(org_id):
        return jsonify({"error": "Number does not belong to this organization"}), 404

    revoke_sip_user(pn)

    if pn.twilio_sid:
        try:
            twilio_client.clear_number_voice_webhook(pn.twilio_sid)
        except twilio_client.TwilioClientError as exc:
            logger.warning("Failed to clear webhook: %s", exc)

    db.session.delete(pn)
    db.session.commit()
    return "", 204


# --- Organization admin assignment (superadmin grants org-admin role) ---

@admin_bp.route("/organizations/<uuid:org_id>/admins", methods=["GET"])
def list_organization_admins(org_id):
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


@admin_bp.route("/organizations/<uuid:org_id>/admins", methods=["POST"])
def add_organization_admin(org_id):
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


@admin_bp.route(
    "/organizations/<uuid:org_id>/admins/<uuid:user_id>", methods=["DELETE"]
)
def remove_organization_admin(org_id, user_id):
    membership = OrganizationMembership.query.filter_by(
        organization_id=str(org_id), user_id=str(user_id)
    ).first_or_404()
    db.session.delete(membership)
    db.session.commit()
    return "", 204


# --- Tenants ---

@admin_bp.route("/tenants", methods=["GET"])
def list_tenants():
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    return jsonify([
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "organization_id": str(t.organization_id),
            "organization_name": t.organization.name if t.organization else None,
            "settings": t.settings,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "user_count": t.users.count(),
        }
        for t in tenants
    ])


@admin_bp.route("/tenants", methods=["POST"])
def create_tenant():
    data = request.get_json() or {}
    if not data.get("name") or not data.get("slug") or not data.get("organization_id"):
        return jsonify({
            "error": "name, slug, and organization_id are required",
        }), 400

    if Tenant.query.filter_by(slug=data["slug"]).first():
        return jsonify({"error": "slug already exists"}), 409

    org = Organization.query.filter_by(id=data["organization_id"]).first()
    if not org:
        return jsonify({"error": "Organization not found"}), 404

    api_key = secrets.token_urlsafe(32)
    tenant = Tenant(
        organization_id=org.id,
        name=data["name"],
        slug=data["slug"],
        settings=data.get("settings", {}),
        api_key_hash=hashlib.sha256(api_key.encode()).hexdigest(),
    )
    db.session.add(tenant)
    db.session.commit()

    return jsonify({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "organization_id": str(tenant.organization_id),
        "api_key": api_key,
    }), 201


@admin_bp.route("/tenants/<uuid:tenant_id>", methods=["PUT"])
def update_tenant(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    data = request.get_json()

    if "name" in data:
        tenant.name = data["name"]
    if "settings" in data:
        tenant.settings = data["settings"]

    db.session.commit()
    return jsonify({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "settings": tenant.settings,
    })


def cascade_delete_tenant(tenant: Tenant) -> None:
    """Delete a tenant and all of its dependent rows. Returns phone numbers
    to the org pool (rather than deleting them) and also revokes any SIP
    credentials attached to those numbers, since they were minted against
    this tenant's SIP Domain.
    """
    from callisto.api.organizations import revoke_sip_user
    from callisto.models import Call, CallSummary, Insight, InsightTemplate, Transcript

    # Delete in FK order: summaries, insights, transcripts, calls, templates, users
    call_ids = [c.id for c in Call.query.filter_by(tenant_id=tenant.id).all()]
    if call_ids:
        CallSummary.query.filter(CallSummary.call_id.in_(call_ids)).delete()
        Insight.query.filter(Insight.call_id.in_(call_ids)).delete()
        Transcript.query.filter(Transcript.call_id.in_(call_ids)).delete()
    Call.query.filter_by(tenant_id=tenant.id).delete()
    InsightTemplate.query.filter_by(tenant_id=tenant.id).delete()
    # Revoke SIP credentials before unlinking the numbers from the tenant —
    # revoke_sip_user reads pn.tenant_id to find the cred list.
    for pn in PhoneNumber.query.filter_by(tenant_id=tenant.id).all():
        revoke_sip_user(pn)
        pn.inbound_enabled = False
        pn.outbound_enabled = False
        pn.inbound_mode = "none"
        pn.inbound_forward_to = None
    PhoneNumber.query.filter_by(tenant_id=tenant.id).update({"tenant_id": None})
    User.query.filter_by(tenant_id=tenant.id).update({"tenant_id": None})
    db.session.delete(tenant)


@admin_bp.route("/tenants/<uuid:tenant_id>", methods=["DELETE"])
def delete_tenant(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    cascade_delete_tenant(tenant)
    db.session.commit()
    return "", 204


# --- Users ---

@admin_bp.route("/users", methods=["GET"])
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "is_superadmin": u.is_superadmin,
            "tenant_id": str(u.tenant_id) if u.tenant_id else None,
            "tenant_name": u.tenant.name if u.tenant else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ])


@admin_bp.route("/users/<uuid:user_id>", methods=["PUT"])
def update_user(user_id):
    user = db.get_or_404(User, user_id)
    data = request.get_json()

    if "tenant_id" in data:
        # Validate tenant exists if not None
        tid = data["tenant_id"]
        if tid is not None:
            tenant = db.session.get(Tenant, tid)
            if not tenant:
                return jsonify({"error": "Tenant not found"}), 404
        user.tenant_id = tid

    if "is_superadmin" in data:
        user.is_superadmin = data["is_superadmin"]

    db.session.commit()
    return jsonify({
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "is_superadmin": user.is_superadmin,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "tenant_name": user.tenant.name if user.tenant else None,
    })


@admin_bp.route("/users/<uuid:user_id>", methods=["DELETE"])
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    db.session.delete(user)
    db.session.commit()
    return "", 204
