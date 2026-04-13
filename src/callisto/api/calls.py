from flask import jsonify, request

from callisto.api import bp
from callisto.extensions import db
from callisto.models import Call, CallSummary, Insight, Transcript


def _serialize_call_list_item(c: Call) -> dict:
    """Serialize a call for list views — includes topics from summary."""
    topics = []
    if c.summary and c.summary.key_topics:
        topics = c.summary.key_topics[:3]

    return {
        "id": str(c.id),
        "external_id": c.external_id,
        "source": c.source,
        "direction": c.direction,
        "caller_number": c.caller_number,
        "contact_id": str(c.contact_id) if c.contact_id else None,
        "contact_name": c.contact.name if c.contact else None,
        "contact_company": c.contact.company if c.contact else None,
        "status": c.status,
        "started_at": c.started_at.isoformat(),
        "ended_at": c.ended_at.isoformat() if c.ended_at else None,
        "duration_sec": c.duration_sec,
        "notes": c.notes,
        "topics": topics,
        "sentiment": c.summary.sentiment if c.summary else None,
        "summary_text": c.summary.summary if c.summary else None,
    }


@bp.route("/tenants/<uuid:tenant_id>/calls", methods=["GET"])
def list_calls(tenant_id):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Call.query.filter_by(tenant_id=tenant_id).order_by(Call.started_at.desc())

    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "calls": [_serialize_call_list_item(c) for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })


@bp.route("/calls/<uuid:call_id>", methods=["GET"])
def get_call(call_id):
    call = db.get_or_404(Call, call_id)
    return jsonify({
        "id": str(call.id),
        "tenant_id": str(call.tenant_id),
        "external_id": call.external_id,
        "source": call.source,
        "direction": call.direction,
        "caller_number": call.caller_number,
        "contact_id": str(call.contact_id) if call.contact_id else None,
        "contact_name": call.contact.name if call.contact else None,
        "contact_company": call.contact.company if call.contact else None,
        "agent_id": call.agent_id,
        "status": call.status,
        "started_at": call.started_at.isoformat(),
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_sec": call.duration_sec,
        "consent_given": call.consent_given,
        "notes": call.notes,
    })


@bp.route("/calls/<uuid:call_id>/notes", methods=["PUT"])
def update_call_notes(call_id):
    call = db.get_or_404(Call, call_id)
    data = request.get_json()
    call.notes = data.get("notes", "")
    db.session.commit()
    return jsonify({"notes": call.notes})


@bp.route("/calls/<uuid:call_id>/transcript", methods=["GET"])
def get_transcript(call_id):
    chunks = (
        Transcript.query
        .filter_by(call_id=call_id)
        .order_by(Transcript.chunk_index)
        .all()
    )
    return jsonify([
        {
            "speaker": c.speaker,
            "text": c.text,
            "start_ms": c.start_ms,
            "end_ms": c.end_ms,
            "confidence": c.confidence,
            "chunk_index": c.chunk_index,
        }
        for c in chunks
    ])


@bp.route("/calls/<uuid:call_id>/insights", methods=["GET"])
def get_call_insights(call_id):
    insights = (
        Insight.query
        .filter_by(call_id=call_id)
        .order_by(Insight.detected_at)
        .all()
    )
    return jsonify([
        {
            "id": str(i.id),
            "template_id": str(i.template_id),
            "source": i.source,
            "detected_at": i.detected_at.isoformat() if i.detected_at else None,
            "confidence": i.confidence,
            "evidence": i.evidence,
            "result": i.result,
            "transcript_range": i.transcript_range,
        }
        for i in insights
    ])


@bp.route("/calls/<uuid:call_id>/summary", methods=["GET"])
def get_call_summary(call_id):
    summary = CallSummary.query.filter_by(call_id=call_id).first()
    if not summary:
        return jsonify({"error": "No summary available for this call"}), 404

    return jsonify({
        "call_id": str(summary.call_id),
        "summary": summary.summary,
        "sentiment": summary.sentiment,
        "key_topics": summary.key_topics,
        "action_items": summary.action_items,
        "llm_model": summary.llm_model,
        "token_cost": summary.token_cost,
        "created_at": summary.created_at.isoformat() if summary.created_at else None,
    })
