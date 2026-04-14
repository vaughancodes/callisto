"""Twilio webhook endpoints.

/webhooks/twilio/voice — called by Twilio when a call arrives at your number.
Returns TwiML that starts a Media Stream to the ingestion WebSocket server.
"""

import logging

from flask import Blueprint, Response, request

from callisto.config import Config
from callisto.extensions import db
from callisto.models import Tenant

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/webhooks/twilio/voice", methods=["POST"])
def twilio_voice_webhook():
    """Handle an incoming Twilio voice call.

    Twilio POSTs call metadata (CallSid, From, To, etc.) when a call arrives
    at a configured phone number. We look up which tenant owns the called number,
    then return TwiML that tells Twilio to fork the audio to our WebSocket
    ingestion server and connect the call to the destination.
    """
    call_sid = request.form.get("CallSid", "")
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")
    direction = request.form.get("Direction", "inbound")

    # Look up tenant by the Twilio number that was called.
    # Tenants store their numbers in settings.twilio_numbers (JSON array).
    logger.info("Twilio webhook: CallSid=%s From=%s To=%s", call_sid, from_number, to_number)

    # Try JSONB array containment: settings->'twilio_numbers' @> '["<number>"]'
    from sqlalchemy import cast, text
    from sqlalchemy.dialects.postgresql import JSONB as JSONB_TYPE
    tenant = Tenant.query.filter(
        Tenant.settings["twilio_numbers"].astext.contains(to_number)
    ).first()

    # Fallback: scan all tenants (small table, fine for MVP)
    if not tenant:
        for t in Tenant.query.all():
            numbers = t.settings.get("twilio_numbers", [])
            if to_number in numbers:
                tenant = t
                break

    if not tenant:
        logger.warning("No tenant found for number %s", to_number)
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>This number is not configured.</Say><Hangup/></Response>",
            content_type="text/xml",
        )

    # Determine where to forward the call
    forward_to = tenant.settings.get("forward_to", "")
    ws_host = Config.INGESTION_WS_HOST
    ws_scheme = "wss" if "ngrok" in ws_host or ":" not in ws_host else "ws"

    # Build the call body — if forward_to is set, dial it; otherwise keep
    # the call alive with a long pause so the stream stays open for testing.
    if forward_to:
        call_body = f"<Dial>{forward_to}</Dial>"
    else:
        # 12 hours of pause — call stays open until the caller hangs up
        call_body = '<Pause length="43200"/>'

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="{ws_scheme}://{ws_host}/ws/twilio/stream" track="both_tracks">
            <Parameter name="tenant_id" value="{tenant.id}"/>
            <Parameter name="from" value="{from_number}"/>
            <Parameter name="to" value="{to_number}"/>
            <Parameter name="direction" value="{direction}"/>
        </Stream>
    </Start>
    {call_body}
</Response>"""

    return Response(twiml.strip(), content_type="text/xml")


@webhooks_bp.route("/webhooks/twilio/status", methods=["POST"])
def twilio_status_callback():
    """Handle Twilio call status updates (ringing, in-progress, completed, etc.).

    This is a secondary signal — the primary call lifecycle is handled via
    the WebSocket start/stop events. This catches edge cases where the
    WebSocket drops before stop is sent.
    """
    from callisto.models import Call

    call_sid = request.form.get("CallSid", "")
    call_status = request.form.get("CallStatus", "")

    if call_status in ("completed", "canceled", "failed", "no-answer", "busy"):
        call = Call.query.filter_by(external_id=call_sid).first()
        if call and call.status == "active":
            call.status = "completed" if call_status == "completed" else "failed"
            duration = request.form.get("CallDuration")
            if duration:
                call.duration_sec = int(duration)
            db.session.commit()

    return Response("", status=204)
