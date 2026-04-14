"""Tenant settings endpoints — name, description, context, and member management.

Access: tenant admins and superadmins.
"""

import re
import secrets

from flask import g, jsonify, request
from sqlalchemy.orm.attributes import flag_modified

from callisto import twilio_client
from callisto.api import bp
from callisto.auth.middleware import require_tenant_admin
from callisto.config import Config
from callisto.extensions import db
from callisto.models import PhoneNumber, Tenant, TenantMembership, User


def _serialize_tenant(t: Tenant) -> dict:
    settings = t.settings or {}
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "description": t.description,
        "context": t.context,
        "forward_to": settings.get("forward_to", ""),
        "twilio_numbers": settings.get("twilio_numbers", []),
        "settings": settings,
    }


def _serialize_member(m: TenantMembership) -> dict:
    return {
        "user_id": str(m.user_id),
        "tenant_id": str(m.tenant_id),
        "email": m.user.email,
        "name": m.user.name,
        "is_admin": m.is_admin,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@bp.route("/tenants/<uuid:tenant_id>/settings", methods=["GET"])
def get_tenant_settings(tenant_id):
    require_tenant_admin(tenant_id)
    tenant = db.get_or_404(Tenant, tenant_id)
    return jsonify(_serialize_tenant(tenant))


@bp.route("/tenants/<uuid:tenant_id>/settings", methods=["PUT"])
def update_tenant_settings(tenant_id):
    require_tenant_admin(tenant_id)
    tenant = db.get_or_404(Tenant, tenant_id)
    data = request.get_json() or {}

    if "name" in data:
        tenant.name = data["name"]
    if "description" in data:
        tenant.description = data["description"]
    if "context" in data:
        tenant.context = data["context"]
    if "forward_to" in data:
        if tenant.settings is None:
            tenant.settings = {}
        tenant.settings["forward_to"] = (data["forward_to"] or "").strip()
        flag_modified(tenant, "settings")
    if "settings" in data:
        tenant.settings = data["settings"]

    db.session.commit()
    return jsonify(_serialize_tenant(tenant))


# --- Phone numbers (assigned to this tenant) ---

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
        "sip_username": p.sip_username,
        "has_sip_user": p.sip_username is not None,
        "inbound_mode": p.inbound_mode,
        "inbound_forward_to": p.inbound_forward_to,
    }


def _slugify_for_sip(value: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", (value or "").lower()).strip("-")
    return s or "tenant"


def _ensure_sip_domain(tenant: Tenant) -> tuple[str, str]:
    """Make sure the tenant has a Twilio SIP Domain and credential list,
    correctly configured for both incoming call auth AND device registration.
    Idempotent — safe to call on existing domains. Returns
    (domain_name, credential_list_sid).
    """
    if tenant.sip_domain_sid and tenant.sip_credential_list_sid and tenant.sip_domain_name:
        # Existing domain — defensively make sure registration is enabled and
        # the credential list is mapped for both calls and registrations.
        # (Legacy domains created before the registration fix won't have these.)
        twilio_client.enable_sip_registration(tenant.sip_domain_sid)
        twilio_client.map_credential_list_for_calls(
            domain_sid=tenant.sip_domain_sid,
            list_sid=tenant.sip_credential_list_sid,
        )
        twilio_client.map_credential_list_for_registrations(
            domain_sid=tenant.sip_domain_sid,
            list_sid=tenant.sip_credential_list_sid,
        )
        return tenant.sip_domain_name, tenant.sip_credential_list_sid

    base = _slugify_for_sip(f"callisto-{tenant.slug}")
    # Twilio SIP Domain names must be globally unique, so include some entropy
    suffix = secrets.token_hex(3)
    domain_name = f"{base}-{suffix}"

    domain_sid = twilio_client.create_sip_domain(
        friendly_name=f"Callisto / {tenant.name}",
        domain_name=domain_name,
        tenant_id=str(tenant.id),
    )
    list_sid = twilio_client.create_sip_credential_list(
        friendly_name=f"Callisto / {tenant.name}"
    )
    twilio_client.map_credential_list_for_calls(
        domain_sid=domain_sid, list_sid=list_sid
    )
    twilio_client.map_credential_list_for_registrations(
        domain_sid=domain_sid, list_sid=list_sid
    )

    tenant.sip_domain_sid = domain_sid
    tenant.sip_domain_name = f"{domain_name}.sip.twilio.com"
    tenant.sip_credential_list_sid = list_sid
    db.session.commit()
    return tenant.sip_domain_name, list_sid


@bp.route("/tenants/<uuid:tenant_id>/numbers", methods=["GET"])
def list_tenant_numbers(tenant_id):
    require_tenant_admin(tenant_id)
    numbers = (
        PhoneNumber.query.filter_by(tenant_id=str(tenant_id))
        .order_by(PhoneNumber.e164)
        .all()
    )
    return jsonify([_serialize_phone_number(p) for p in numbers])


@bp.route(
    "/tenants/<uuid:tenant_id>/numbers/<uuid:number_id>", methods=["PUT"]
)
def update_tenant_number(tenant_id, number_id):
    """Toggle inbound/outbound flags for one of this tenant's numbers."""
    require_tenant_admin(tenant_id)
    pn = db.get_or_404(PhoneNumber, number_id)
    if str(pn.tenant_id) != str(tenant_id):
        return jsonify({"error": "Number is not assigned to this tenant"}), 404

    data = request.get_json() or {}
    if "inbound_enabled" in data:
        pn.inbound_enabled = bool(data["inbound_enabled"])
    if "outbound_enabled" in data:
        pn.outbound_enabled = bool(data["outbound_enabled"])
    if "friendly_name" in data:
        fn = (data["friendly_name"] or "").strip() or None
        pn.friendly_name = fn
    if "inbound_mode" in data:
        mode = (data["inbound_mode"] or "none").strip()
        if mode not in ("none", "sip", "forward"):
            return jsonify({"error": f"Invalid inbound_mode: {mode}"}), 400
        if mode == "sip" and not pn.sip_username:
            return jsonify({
                "error": "Cannot set inbound_mode=sip without a SIP user assigned to this number.",
            }), 400
        pn.inbound_mode = mode
    if "inbound_forward_to" in data:
        ift = (data["inbound_forward_to"] or "").strip() or None
        pn.inbound_forward_to = ift
    db.session.commit()
    return jsonify(_serialize_phone_number(pn))


@bp.route(
    "/tenants/<uuid:tenant_id>/numbers/<uuid:number_id>/sip-user",
    methods=["POST"],
)
def create_sip_user_for_number(tenant_id, number_id):
    """Mint a SIP credential for this phone number. Returns the password
    exactly once — Twilio will not reveal it again.
    """
    require_tenant_admin(tenant_id)
    pn = db.get_or_404(PhoneNumber, number_id)
    if str(pn.tenant_id) != str(tenant_id):
        return jsonify({"error": "Number is not assigned to this tenant"}), 404
    if pn.sip_username:
        return jsonify({
            "error": "This number already has a SIP user. Delete it first to mint new credentials.",
        }), 409

    tenant = db.session.get(Tenant, tenant_id)

    try:
        domain_name, list_sid = _ensure_sip_domain(tenant)
    except twilio_client.TwilioClientError as exc:
        return jsonify({"error": str(exc)}), 502

    # Username derived from the E.164 number (digits only, no +)
    username = pn.e164.lstrip("+")
    password = secrets.token_urlsafe(24)

    try:
        cred_sid = twilio_client.create_sip_credential(
            list_sid=list_sid, username=username, password=password
        )
    except twilio_client.TwilioClientError as exc:
        return jsonify({"error": str(exc)}), 502

    pn.sip_username = username
    pn.sip_credential_sid = cred_sid
    db.session.commit()

    return jsonify({
        "username": username,
        "password": password,  # shown ONCE — caller must surface it carefully
        "sip_domain": domain_name,
        "sip_uri": f"sip:{username}@{domain_name}",
    }), 201


@bp.route(
    "/tenants/<uuid:tenant_id>/numbers/<uuid:number_id>/sip-user",
    methods=["DELETE"],
)
def delete_sip_user_for_number(tenant_id, number_id):
    require_tenant_admin(tenant_id)
    pn = db.get_or_404(PhoneNumber, number_id)
    if str(pn.tenant_id) != str(tenant_id):
        return jsonify({"error": "Number is not assigned to this tenant"}), 404
    if not pn.sip_credential_sid:
        return jsonify({"error": "No SIP user on this number"}), 404

    tenant = db.session.get(Tenant, tenant_id)
    if tenant and tenant.sip_credential_list_sid:
        try:
            twilio_client.delete_sip_credential(
                list_sid=tenant.sip_credential_list_sid,
                credential_sid=pn.sip_credential_sid,
            )
        except twilio_client.TwilioClientError as exc:
            return jsonify({"error": str(exc)}), 502

    pn.sip_username = None
    pn.sip_credential_sid = None
    # If inbound was routing to this SIP user, fall back to none
    if pn.inbound_mode == "sip":
        pn.inbound_mode = "none"
    db.session.commit()
    return "", 204


# --- Member management ---

@bp.route("/tenants/<uuid:tenant_id>/members", methods=["GET"])
def list_members(tenant_id):
    require_tenant_admin(tenant_id)
    members = (
        TenantMembership.query.filter_by(tenant_id=tenant_id)
        .join(User, TenantMembership.user_id == User.id)
        .order_by(User.name)
        .all()
    )
    return jsonify([_serialize_member(m) for m in members])


@bp.route("/tenants/<uuid:tenant_id>/members", methods=["POST"])
def add_member(tenant_id):
    require_tenant_admin(tenant_id)
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    is_admin = bool(data.get("is_admin", False))

    if not email:
        return jsonify({"error": "email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            "error": "No user with that email exists. They must sign in at least once first.",
        }), 404

    existing = TenantMembership.query.filter_by(
        user_id=user.id, tenant_id=tenant_id
    ).first()
    if existing:
        return jsonify({"error": "User is already a member of this tenant"}), 409

    membership = TenantMembership(
        user_id=user.id, tenant_id=tenant_id, is_admin=is_admin
    )
    db.session.add(membership)
    db.session.commit()
    return jsonify(_serialize_member(membership)), 201


@bp.route("/tenants/<uuid:tenant_id>/members/<uuid:user_id>", methods=["PUT"])
def update_member(tenant_id, user_id):
    require_tenant_admin(tenant_id)
    membership = TenantMembership.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first_or_404()
    data = request.get_json() or {}

    if "is_admin" in data:
        membership.is_admin = bool(data["is_admin"])

    db.session.commit()
    return jsonify(_serialize_member(membership))


@bp.route("/tenants/<uuid:tenant_id>/members/<uuid:user_id>", methods=["DELETE"])
def remove_member(tenant_id, user_id):
    require_tenant_admin(tenant_id)
    membership = TenantMembership.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first_or_404()

    # If removing the user's currently-active tenant, clear their tenant_id
    user = db.session.get(User, user_id)
    if user and str(user.tenant_id) == str(tenant_id):
        user.tenant_id = None

    db.session.delete(membership)
    db.session.commit()
    return "", 204
