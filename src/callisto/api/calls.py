from flask import g, jsonify, request

from callisto import twilio_client
from callisto.api import bp
from callisto.auth.middleware import is_tenant_member
from callisto.extensions import db
from callisto.models import Call, CallSummary, Insight, PhoneNumber, Transcript


def _our_number_e164(c: Call) -> str | None:
    direction = c.direction or "inbound"
    return c.caller_number if direction.startswith("outbound") else c.callee_number


def _other_party_number(c: Call) -> str | None:
    """The number of the party on the other end of the call: for inbound
    that's the caller, for outbound that's the callee."""
    direction = c.direction or "inbound"
    return c.callee_number if direction.startswith("outbound") else c.caller_number


def _our_number_friendly_name(c: Call) -> str | None:
    our_e164 = _our_number_e164(c)
    if not our_e164:
        return None
    pn = PhoneNumber.query.filter_by(e164=our_e164).first()
    return pn.friendly_name if pn else None


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
        "callee_number": c.callee_number,
        "other_party_number": _other_party_number(c),
        "our_number_friendly_name": _our_number_friendly_name(c),
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
        "callee_number": call.callee_number,
        "other_party_number": _other_party_number(call),
        "our_number_friendly_name": _our_number_friendly_name(call),
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


@bp.route("/calls/<uuid:call_id>/reanalyze", methods=["POST"])
def reanalyze_call(call_id):
    """Re-run the deep analysis + summary pass for a completed call using
    the current templates, tenant context, and prompts."""
    from callisto.tasks import reanalyze_call as reanalyze_task

    call = db.get_or_404(Call, call_id)
    if call.status == "active":
        return jsonify({
            "error": "Cannot re-analyze a call that is still in progress.",
        }), 409

    has_transcript = (
        Transcript.query.filter_by(call_id=call.id).first() is not None
    )
    if not has_transcript:
        return jsonify({
            "error": "Cannot re-analyze — no transcript is available for this call.",
        }), 409

    # Flip status back to "processing" so the UI shows that work is in flight;
    # compute_cost_accounting will set it to "completed" when the chain finishes.
    call.status = "processing"
    db.session.commit()

    reanalyze_task.apply_async(args=[str(call.id)])
    return jsonify({"status": "queued"}), 202


@bp.route("/calls/<uuid:call_id>/transcript", methods=["GET"])
def get_transcript(call_id):
    # Sort chronologically by start time so two-speaker conversations merge
    # correctly across the inbound/outbound tracks.
    chunks = (
        Transcript.query
        .filter_by(call_id=call_id)
        .order_by(Transcript.start_ms, Transcript.chunk_index)
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
            "template_name": i.template.name if i.template else None,
            "template_severity": i.template.severity if i.template else None,
            "source": i.source,
            "detected_at": i.detected_at.isoformat() if i.detected_at else None,
            "confidence": i.confidence,
            "evidence": i.evidence,
            "result": i.result,
            "transcript_range": i.transcript_range,
        }
        for i in insights
    ])


@bp.route("/tenants/<uuid:tenant_id>/calls/outbound", methods=["POST"])
def initiate_outbound_call(tenant_id):
    """Place an outbound call from one of the tenant's outbound-enabled
    numbers. Returns the new call's external_id (Twilio Call SID).
    """
    if not is_tenant_member(tenant_id):
        return jsonify({"error": "Tenant access required"}), 403

    data = request.get_json() or {}
    from_number_id = data.get("from_number_id")
    to_number = (data.get("to_number") or "").strip()
    if not from_number_id or not to_number:
        return jsonify({
            "error": "from_number_id and to_number are required",
        }), 400

    pn = PhoneNumber.query.filter_by(id=from_number_id).first()
    if not pn or str(pn.tenant_id) != str(tenant_id):
        return jsonify({"error": "Number is not assigned to this tenant"}), 404
    if not pn.outbound_enabled:
        return jsonify({
            "error": f"{pn.e164} is not enabled for outbound calls",
        }), 400

    try:
        sid = twilio_client.initiate_outbound_call(
            from_e164=pn.e164, to_e164=to_number
        )
    except twilio_client.TwilioClientError as exc:
        return jsonify({"error": str(exc)}), 502

    # The Call row will be created when Twilio hits /webhooks/twilio/voice
    # and the ingestion server receives the Media Stream `start` event.
    return jsonify({
        "external_id": sid,
        "from_number": pn.e164,
        "to_number": to_number,
    }), 202


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
