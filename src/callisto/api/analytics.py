"""Analytics endpoints."""

from datetime import datetime, timedelta

from flask import jsonify, request
from sqlalchemy import func

from callisto.api import bp
from callisto.extensions import db
from callisto.models import Insight, InsightTemplate


@bp.route("/tenants/<uuid:tenant_id>/analytics/insights", methods=["GET"])
def insight_trends(tenant_id):
    """Return insight counts over time, grouped by template and date."""
    days = request.args.get("days", 30, type=int)
    template_id = request.args.get("template_id")
    since = datetime.now() - timedelta(days=days)

    query = (
        db.session.query(
            func.date(Insight.detected_at).label("date"),
            InsightTemplate.name.label("template_name"),
            Insight.template_id,
            func.count(Insight.id).label("count"),
        )
        .join(InsightTemplate, Insight.template_id == InsightTemplate.id)
        .filter(
            Insight.tenant_id == tenant_id,
            Insight.detected_at >= since,
        )
    )

    if template_id:
        query = query.filter(Insight.template_id == template_id)

    results = (
        query
        .group_by(func.date(Insight.detected_at), InsightTemplate.name, Insight.template_id)
        .order_by(func.date(Insight.detected_at))
        .all()
    )

    return jsonify([
        {
            "date": str(r.date),
            "template_name": r.template_name,
            "template_id": str(r.template_id),
            "count": r.count,
        }
        for r in results
    ])
