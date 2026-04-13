"""Superadmin API endpoints for managing tenants and users."""

import hashlib
import secrets

from flask import Blueprint, jsonify, request

from callisto.auth.middleware import require_superadmin
from callisto.extensions import db
from callisto.models import Tenant
from callisto.models.user import User

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
def check_superadmin():
    require_superadmin()


# --- Tenants ---

@admin_bp.route("/tenants", methods=["GET"])
def list_tenants():
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    return jsonify([
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "settings": t.settings,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "user_count": t.users.count(),
        }
        for t in tenants
    ])


@admin_bp.route("/tenants", methods=["POST"])
def create_tenant():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("slug"):
        return jsonify({"error": "name and slug are required"}), 400

    if Tenant.query.filter_by(slug=data["slug"]).first():
        return jsonify({"error": "slug already exists"}), 409

    api_key = secrets.token_urlsafe(32)
    tenant = Tenant(
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


@admin_bp.route("/tenants/<uuid:tenant_id>", methods=["DELETE"])
def delete_tenant(tenant_id):
    from callisto.models import Call, CallSummary, Insight, InsightTemplate, Transcript

    tenant = db.get_or_404(Tenant, tenant_id)

    # Delete in FK order: summaries, insights, transcripts, calls, templates, users
    call_ids = [c.id for c in Call.query.filter_by(tenant_id=tenant.id).all()]
    if call_ids:
        CallSummary.query.filter(CallSummary.call_id.in_(call_ids)).delete()
        Insight.query.filter(Insight.call_id.in_(call_ids)).delete()
        Transcript.query.filter(Transcript.call_id.in_(call_ids)).delete()
    Call.query.filter_by(tenant_id=tenant.id).delete()
    InsightTemplate.query.filter_by(tenant_id=tenant.id).delete()
    User.query.filter_by(tenant_id=tenant.id).update({"tenant_id": None})
    db.session.delete(tenant)
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
