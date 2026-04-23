from flask import jsonify, request

from callisto.api import bp
from callisto.extensions import db
from callisto.models import InsightTemplate, TemplateCategory

_VALID_APPLIES_TO = {"external", "internal", "both"}


def _ensure_category(tenant_id, name: str) -> TemplateCategory | None:
    """Return the TemplateCategory for (tenant_id, name), creating it if it
    doesn't exist. Returns None if name is blank."""
    name = (name or "").strip()
    if not name:
        return None
    existing = TemplateCategory.query.filter_by(
        tenant_id=tenant_id, name=name
    ).first()
    if existing:
        return existing
    category = TemplateCategory(tenant_id=tenant_id, name=name)
    db.session.add(category)
    db.session.flush()
    return category


def _serialize_template(t: InsightTemplate) -> dict:
    return {
        "id": str(t.id),
        "tenant_id": str(t.tenant_id),
        "name": t.name,
        "description": t.description,
        "prompt": t.prompt,
        "category": t.category,
        "severity": t.severity,
        "is_realtime": t.is_realtime,
        "inbound_enabled": t.inbound_enabled,
        "outbound_enabled": t.outbound_enabled,
        "applies_to": t.applies_to,
        "output_schema": t.output_schema,
        "active": t.active,
    }


@bp.route("/tenants/<uuid:tenant_id>/templates", methods=["POST"])
def create_template(tenant_id):
    data = request.get_json()
    if not data or not data.get("name") or not data.get("prompt"):
        return jsonify({"error": "name and prompt are required"}), 400

    applies_to = data.get("applies_to", "both")
    if applies_to not in _VALID_APPLIES_TO:
        return jsonify({
            "error": "applies_to must be one of: external, internal, both"
        }), 400

    category_name = (data.get("category") or "").strip() or "custom"
    _ensure_category(tenant_id, category_name)

    template = InsightTemplate(
        tenant_id=tenant_id,
        name=data["name"],
        description=data.get("description"),
        prompt=data["prompt"],
        category=category_name,
        severity=data.get("severity", "info"),
        is_realtime=data.get("is_realtime", True),
        inbound_enabled=data.get("inbound_enabled", True),
        outbound_enabled=data.get("outbound_enabled", True),
        applies_to=applies_to,
        output_schema=data.get("output_schema"),
    )
    db.session.add(template)
    db.session.commit()

    return jsonify(_serialize_template(template)), 201


@bp.route("/tenants/<uuid:tenant_id>/templates", methods=["GET"])
def list_templates(tenant_id):
    templates = InsightTemplate.query.filter_by(tenant_id=tenant_id, active=True).all()
    return jsonify([_serialize_template(t) for t in templates])


@bp.route("/templates/<uuid:template_id>", methods=["PUT"])
def update_template(template_id):
    template = db.get_or_404(InsightTemplate, template_id)
    data = request.get_json()

    if "applies_to" in data and data["applies_to"] not in _VALID_APPLIES_TO:
        return jsonify({
            "error": "applies_to must be one of: external, internal, both"
        }), 400

    if "category" in data:
        category_name = (data.get("category") or "").strip() or "custom"
        _ensure_category(template.tenant_id, category_name)
        data["category"] = category_name

    for field in ("name", "description", "prompt", "category", "severity",
                  "is_realtime", "inbound_enabled", "outbound_enabled",
                  "applies_to", "output_schema", "active"):
        if field in data:
            setattr(template, field, data[field])

    db.session.commit()
    return jsonify(_serialize_template(template))


@bp.route("/templates/<uuid:template_id>", methods=["DELETE"])
def delete_template(template_id):
    template = db.get_or_404(InsightTemplate, template_id)
    template.active = False
    db.session.commit()
    return "", 204
