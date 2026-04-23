"""Per-tenant template category CRUD."""

from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from callisto.api import bp
from callisto.extensions import db
from callisto.models import InsightTemplate, TemplateCategory


def _serialize(c: TemplateCategory) -> dict:
    return {
        "id": str(c.id),
        "tenant_id": str(c.tenant_id),
        "name": c.name,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@bp.route("/tenants/<uuid:tenant_id>/template-categories", methods=["GET"])
def list_categories(tenant_id):
    categories = (
        TemplateCategory.query
        .filter_by(tenant_id=tenant_id)
        .order_by(TemplateCategory.name)
        .all()
    )
    return jsonify([_serialize(c) for c in categories])


@bp.route("/tenants/<uuid:tenant_id>/template-categories", methods=["POST"])
def create_category(tenant_id):
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    category = TemplateCategory(tenant_id=tenant_id, name=name)
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": f"A category named '{name}' already exists.",
        }), 409
    return jsonify(_serialize(category)), 201


@bp.route("/template-categories/<uuid:category_id>", methods=["PUT"])
def update_category(category_id):
    category = db.get_or_404(TemplateCategory, category_id)
    data = request.get_json() or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return jsonify({"error": "name is required"}), 400

    if new_name == category.name:
        return jsonify(_serialize(category))

    old_name = category.name
    category.name = new_name
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": f"A category named '{new_name}' already exists.",
        }), 409

    # Keep denormalized InsightTemplate.category in sync with the rename.
    InsightTemplate.query.filter_by(
        tenant_id=category.tenant_id, category=old_name
    ).update({"category": new_name}, synchronize_session=False)

    db.session.commit()
    return jsonify(_serialize(category))


@bp.route("/template-categories/<uuid:category_id>", methods=["DELETE"])
def delete_category(category_id):
    category = db.get_or_404(TemplateCategory, category_id)

    in_use = InsightTemplate.query.filter_by(
        tenant_id=category.tenant_id, category=category.name, active=True
    ).count()
    if in_use > 0:
        return jsonify({
            "error": (
                f"Cannot delete '{category.name}' — {in_use} active template"
                f"{'s' if in_use != 1 else ''} still use this category."
            ),
        }), 409

    db.session.delete(category)
    db.session.commit()
    return "", 204
