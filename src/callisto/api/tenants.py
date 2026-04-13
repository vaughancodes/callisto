import hashlib
import secrets

from flask import jsonify, request

from callisto.api import bp
from callisto.extensions import db
from callisto.models import Tenant


@bp.route("/tenants", methods=["POST"])
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


@bp.route("/tenants/<uuid:tenant_id>", methods=["GET"])
def get_tenant(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    return jsonify({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "settings": tenant.settings,
        "created_at": tenant.created_at.isoformat(),
    })


@bp.route("/tenants/<uuid:tenant_id>", methods=["PUT"])
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
