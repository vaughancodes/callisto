"""Tenant settings endpoints — name, description, context, and member management.

Access: tenant admins and superadmins.
"""

from flask import g, jsonify, request

from callisto.api import bp
from callisto.auth.middleware import require_tenant_admin
from callisto.extensions import db
from callisto.models import Tenant, TenantMembership, User


def _serialize_tenant(t: Tenant) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "description": t.description,
        "context": t.context,
        "settings": t.settings,
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
    if "settings" in data:
        tenant.settings = data["settings"]

    db.session.commit()
    return jsonify(_serialize_tenant(tenant))


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
