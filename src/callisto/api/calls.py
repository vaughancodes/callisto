import io
import os
import wave

from flask import abort, g, jsonify, request, send_file

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


def _voicemail_meta(call: Call) -> dict | None:
    """Pull out the voicemail sub-dict (stamped by the fallback webhook)."""
    meta = call.metadata_ or {}
    vm = meta.get("voicemail")
    return vm if isinstance(vm, dict) and vm.get("started_at") else None


def _voicemail_audio_start_ms(call_id, dial_boundary_ms: int) -> int:
    """The true start of the voicemail audio.

    ``dial_boundary_ms`` is when the Dial action fired (caller hadn't
    picked up yet). Between that boundary and the caller's first word our
    greeting is playing — we don't want that in the playback. We use the
    first external-speaker transcript chunk past the boundary as the
    "caller's first word" and align the audio slice to it. Falls back to
    the boundary itself if nothing's been transcribed yet.
    """
    first = (
        Transcript.query
        .filter(Transcript.call_id == call_id)
        .filter(Transcript.start_ms >= dial_boundary_ms)
        .filter(Transcript.speaker == "external")
        .order_by(Transcript.start_ms, Transcript.chunk_index)
        .first()
    )
    return first.start_ms if first else dial_boundary_ms


def _recording_path_if_exists(call: Call) -> str | None:
    path = (call.metadata_ or {}).get("recording_path")
    if path and os.path.isfile(path):
        return path
    return None


@bp.route("/calls/<uuid:call_id>", methods=["GET"])
def get_call(call_id):
    call = db.get_or_404(Call, call_id)
    vm = _voicemail_meta(call)
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
        "has_voicemail": vm is not None,
        "has_recording": _recording_path_if_exists(call) is not None,
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


@bp.route("/calls/<uuid:call_id>/audio", methods=["GET"])
def get_call_audio(call_id):
    """Serve the full stereo call recording (L=inbound, R=outbound)."""
    call = db.get_or_404(Call, call_id)
    path = _recording_path_if_exists(call)
    if not path:
        abort(404)
    return send_file(
        path,
        mimetype="audio/wav",
        as_attachment=False,
        download_name=f"call-{call_id}.wav",
        conditional=True,
    )


@bp.route("/tenants/<uuid:tenant_id>/voicemails", methods=["GET"])
def list_tenant_voicemails(tenant_id):
    """List calls that have a voicemail on them, newest first."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    # A voicemail is any Call whose metadata has a voicemail.started_at key.
    # JSONB path lookup via SQLAlchemy's `op('->')` is brittle across dialects,
    # so use a JSONB ? containment check which Postgres supports natively.
    query = (
        Call.query
        .filter(Call.tenant_id == tenant_id)
        .filter(Call.metadata_["voicemail"]["started_at"].astext.isnot(None))
        .order_by(Call.started_at.desc())
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    def _serialize(c: Call) -> dict:
        vm = _voicemail_meta(c) or {}
        started_at_ms = int(vm.get("started_at_ms") or 0)
        voicemail_duration = None
        if c.duration_sec is not None:
            remaining = c.duration_sec - (started_at_ms // 1000)
            if remaining > 0:
                voicemail_duration = remaining
        return {
            "call_id": str(c.id),
            "external_id": c.external_id,
            "direction": c.direction,
            "other_party_number": _other_party_number(c),
            "our_number_friendly_name": _our_number_friendly_name(c),
            "contact_id": str(c.contact_id) if c.contact_id else None,
            "contact_name": c.contact.name if c.contact else None,
            "contact_company": c.contact.company if c.contact else None,
            "call_started_at": c.started_at.isoformat(),
            "voicemail_started_at": vm.get("started_at"),
            "voicemail_duration_sec": voicemail_duration,
            "has_recording": _recording_path_if_exists(c) is not None,
        }

    return jsonify({
        "voicemails": [_serialize(c) for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })


@bp.route("/calls/<uuid:call_id>/voicemail", methods=["GET"])
def get_call_voicemail(call_id):
    """Metadata + transcript slice for the voicemail portion of a call.

    The voicemail is the tail of the call after the Dial action fired —
    when the destination didn't pick up and our fallback TwiML took over.
    The media stream keeps running through the voicemail, so the transcript
    chunks past ``voicemail.started_at_ms`` are the voicemail transcript.
    """
    call = db.get_or_404(Call, call_id)
    vm = _voicemail_meta(call)
    if vm is None:
        return jsonify({"error": "No voicemail on this call"}), 404

    dial_boundary_ms = int(vm.get("started_at_ms") or 0)
    audio_start_ms = _voicemail_audio_start_ms(call_id, dial_boundary_ms)

    # Only the external (caller) track — the internal track picks up the
    # <Play>ed greeting audio, which we don't want in the voicemail transcript.
    chunks = (
        Transcript.query
        .filter(Transcript.call_id == call_id)
        .filter(Transcript.start_ms >= audio_start_ms)
        .filter(Transcript.speaker == "external")
        .order_by(Transcript.start_ms, Transcript.chunk_index)
        .all()
    )

    recording_path = (call.metadata_ or {}).get("recording_path")
    has_recording = bool(recording_path and os.path.isfile(recording_path))

    voicemail_duration_sec = None
    if call.duration_sec is not None:
        remaining = call.duration_sec - (audio_start_ms // 1000)
        if remaining > 0:
            voicemail_duration_sec = remaining

    return jsonify({
        "started_at": vm.get("started_at"),
        # started_at_ms is the aligned boundary used for both the audio
        # slice and the transcript rebasing — client rebases timestamps
        # against this value so transcript and playback stay in sync.
        "started_at_ms": audio_start_ms,
        "dial_status": vm.get("dial_status"),
        "duration_sec": voicemail_duration_sec,
        "has_recording": has_recording,
        "transcript": [
            {
                "speaker": c.speaker,
                "text": c.text,
                "start_ms": c.start_ms,
                "end_ms": c.end_ms,
                "confidence": c.confidence,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ],
    })


@bp.route("/calls/<uuid:call_id>/voicemail/audio", methods=["GET"])
def get_call_voicemail_audio(call_id):
    """Stream just the voicemail portion of the full-call WAV.

    Starts at the caller's first transcribed word past the Dial-timeout
    boundary so the greeting isn't included, and emits mono (inbound /
    external track only) so any residual right-channel greeting audio
    can't bleed through. Falls back to the dial-timeout boundary when
    no external transcript chunks exist yet.
    """
    call = db.get_or_404(Call, call_id)
    vm = _voicemail_meta(call)
    if vm is None:
        abort(404)

    recording_path = (call.metadata_ or {}).get("recording_path")
    if not recording_path or not os.path.isfile(recording_path):
        abort(404)

    dial_boundary_ms = int(vm.get("started_at_ms") or 0)
    audio_start_ms = _voicemail_audio_start_ms(call_id, dial_boundary_ms)

    with wave.open(recording_path, "rb") as src:
        framerate = src.getframerate()
        nchannels = src.getnchannels()
        sampwidth = src.getsampwidth()
        total_frames = src.getnframes()

        start_frame = min(
            total_frames,
            int(audio_start_ms * framerate / 1000),
        )
        remaining = total_frames - start_frame
        if remaining <= 0:
            abort(404)

        src.setpos(start_frame)
        frames = src.readframes(remaining)

    # Downmix to mono-inbound. The ingestion server writes stereo with
    # L=inbound (caller), R=outbound (our greeting). Keeping only the
    # left channel guarantees no greeting bleeds into the voicemail
    # playback even if the offset math is slightly off.
    if nchannels >= 2:
        frame_size = nchannels * sampwidth
        mono = bytearray(len(frames) // nchannels)
        for i in range(0, len(frames), frame_size):
            mono[(i // nchannels):(i // nchannels) + sampwidth] = (
                frames[i:i + sampwidth]
            )
        frames = bytes(mono)
        out_channels = 1
    else:
        out_channels = nchannels

    out = io.BytesIO()
    with wave.open(out, "wb") as dst:
        dst.setnchannels(out_channels)
        dst.setsampwidth(sampwidth)
        dst.setframerate(framerate)
        dst.writeframes(frames)
    out.seek(0)

    return send_file(
        out,
        mimetype="audio/wav",
        as_attachment=False,
        download_name=f"voicemail-{call_id}.wav",
    )


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
