"""Twilio webhook endpoints.

/webhooks/twilio/voice — called by Twilio when a call arrives at one of our
numbers (inbound) OR when an outbound call we initiated via the REST API
connects. Returns TwiML that starts a Media Stream to the ingestion server.
"""

import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, Response, abort, request, send_file
from sqlalchemy.orm.attributes import flag_modified

from callisto.config import Config
from callisto.extensions import db
from callisto.models import Call, PhoneNumber, Tenant

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", __name__)


def _is_outbound(direction: str) -> bool:
    return direction.startswith("outbound")


def _extract_dialed_number(raw_to: str) -> str:
    """Pull the dialed number out of whatever Twilio sent in `To`.

    SIP softphones send things like `sip:+15551234567@tenant.sip.twilio.com`
    or `sip:5551234567@tenant.sip.twilio.com`. We strip the SIP wrapper and
    do a small heuristic to coerce the result into E.164.
    """
    s = raw_to or ""
    if s.startswith("sip:"):
        s = s[4:]
    if "@" in s:
        s = s.split("@", 1)[0]
    s = s.strip()
    if not s:
        return s
    if s.startswith("+"):
        return s
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return s
    if len(digits) == 10:
        return "+1" + digits
    return "+" + digits


@webhooks_bp.route("/webhooks/twilio/voice", methods=["POST"])
def twilio_voice_webhook():
    """Twilio POSTs here for both inbound and outbound calls. We figure out
    which of our numbers is involved, look up the owning tenant, and return
    TwiML that forks the audio to the Media Stream server.
    """
    call_sid = request.form.get("CallSid", "")
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")
    direction = request.form.get("Direction", "inbound")

    logger.info(
        "Twilio webhook: CallSid=%s Direction=%s From=%s To=%s",
        call_sid, direction, from_number, to_number,
    )

    # Look up the owning tenant + phone number row.
    pn = None
    tenant = None
    sip_originated = False

    # Case 1: SIP-originated outbound call. Twilio puts a SIP URI in `From`,
    # not an E.164. We pass the tenant_id in the webhook URL on the SIP
    # Domain, so read it from the query string here.
    sip_tenant_id = request.args.get("tenant_id")
    if sip_tenant_id and from_number.startswith("sip:"):
        sip_originated = True
        tenant = Tenant.query.filter_by(id=sip_tenant_id).first()
        # Identify which of the tenant's numbers the call should appear on.
        # For SIP-originated outbound, the SIP user owns one number; we look
        # the user up by the SIP URI's localpart.
        sip_user = from_number[len("sip:"):].split("@", 1)[0]
        if tenant:
            pn = PhoneNumber.query.filter_by(
                tenant_id=tenant.id, sip_username=sip_user
            ).first()
    else:
        # Case 2: regular inbound or REST-API outbound. The "our" number is
        # the To (inbound) or the From (outbound).
        our_number = from_number if _is_outbound(direction) else to_number
        pn = PhoneNumber.query.filter_by(e164=our_number).first()
        if pn and pn.tenant_id:
            tenant = db.session.get(Tenant, pn.tenant_id)

    if not tenant:
        logger.warning(
            "No tenant assigned to number %s (direction=%s)", our_number, direction
        )
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>This number is not configured.</Say><Hangup/></Response>",
            content_type="text/xml",
        )

    # SIP-originated calls are always outbound from the user's perspective
    is_outbound_call = sip_originated or _is_outbound(direction)

    # Honor the direction routing flags configured by the tenant admin
    if is_outbound_call and not pn.outbound_enabled:
        logger.warning("Number %s is not enabled for outbound calls", pn.e164)
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Hangup/></Response>",
            content_type="text/xml",
        )
    if not is_outbound_call and not pn.inbound_enabled:
        logger.warning("Number %s is not enabled for inbound calls", pn.e164)
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>This number is not accepting inbound calls.</Say><Hangup/></Response>",
            content_type="text/xml",
        )

    # Derive the Media Stream WebSocket URL from the canonical public base URL
    base = Config.PUBLIC_BASE_URL.rstrip("/")
    if base.startswith("https://"):
        ws_url = "wss://" + base[len("https://"):] + "/ws/twilio/stream"
    elif base.startswith("http://"):
        ws_url = "ws://" + base[len("http://"):] + "/ws/twilio/stream"
    else:
        ws_url = f"wss://{base}/ws/twilio/stream"

    # Build the call body.
    if sip_originated:
        # The SIP device handed Twilio an INVITE; Twilio is asking us
        # what to do with it. Place the actual outbound leg with our
        # phone number as the caller ID.
        dialed = _extract_dialed_number(to_number)
        if not dialed:
            logger.warning(
                "SIP-originated call with empty destination from %s", from_number
            )
            return Response(
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response><Say>No destination dialed.</Say><Hangup/></Response>",
                content_type="text/xml",
            )
        call_body = (
            f'<Dial callerId="{pn.e164}"><Number>{dialed}</Number></Dial>'
        )
    elif _is_outbound(direction):
        # REST-API outbound: Twilio already dialed the destination from
        # Calls.create; just keep the line open while the stream runs.
        call_body = '<Pause length="43200"/>'
    else:
        # Inbound: route based on the per-number inbound mode.
        mode = (pn.inbound_mode or "none") if pn else "none"
        voicemail_app = pn and pn.voicemail_mode == "app"

        # When the app is catching voicemail, we cap the Dial with a short
        # timeout and an action URL. If the destination answers, Twilio
        # ignores the action; if it times out / fails, Twilio hits the
        # action URL which returns the voicemail TwiML.
        if voicemail_app and mode in ("sip", "forward"):
            base_url = Config.PUBLIC_BASE_URL.rstrip("/")
            action_url = (
                f"{base_url}/webhooks/twilio/voicemail/fallback"
                f"?number_id={pn.id}"
            )
            dial_attrs = (
                f' timeout="{Config.VOICEMAIL_DIAL_TIMEOUT_SECONDS}"'
                f' action="{action_url}" method="POST"'
            )
        else:
            dial_attrs = ""

        if mode == "sip" and pn and pn.sip_username and tenant.sip_domain_name:
            sip_uri = f"sip:{pn.sip_username}@{tenant.sip_domain_name}"
            call_body = f"<Dial{dial_attrs}><Sip>{sip_uri}</Sip></Dial>"
        elif mode == "forward" and pn and pn.inbound_forward_to:
            call_body = f"<Dial{dial_attrs}>{pn.inbound_forward_to}</Dial>"
        else:
            # Record-only mode: keep the line open while the stream captures audio
            call_body = '<Pause length="43200"/>'

    # For SIP-originated calls, replace the raw SIP URIs with the resolved
    # E.164 values so the ingestion server stores clean numbers on the Call
    # row and contact matching has something to work with.
    if sip_originated:
        stream_from = pn.e164
        stream_to = _extract_dialed_number(to_number)
        stream_direction = "outbound"
    else:
        stream_from = from_number
        stream_to = to_number
        stream_direction = direction

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="{ws_url}" track="both_tracks">
            <Parameter name="tenant_id" value="{tenant.id}"/>
            <Parameter name="from" value="{stream_from}"/>
            <Parameter name="to" value="{stream_to}"/>
            <Parameter name="direction" value="{stream_direction}"/>
        </Stream>
    </Start>
    {call_body}
</Response>"""

    return Response(twiml.strip(), content_type="text/xml")


def _find_greeting_file(tenant_id) -> str | None:
    """Return the on-disk path of the tenant's greeting audio, or None."""
    d = Config.VOICEMAIL_GREETINGS_DIR
    if not os.path.isdir(d):
        return None
    prefix = f"{tenant_id}."
    for fname in os.listdir(d):
        if fname.startswith(prefix):
            return os.path.join(d, fname)
    return None


@webhooks_bp.route("/webhooks/voicemail/greeting/<uuid:tenant_id>", methods=["GET"])
def voicemail_greeting(tenant_id):
    """Public endpoint — Twilio fetches this with <Play>."""
    path = _find_greeting_file(tenant_id)
    if not path or not os.path.isfile(path):
        abort(404)
    # Infer a reasonable mimetype from the extension.
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    mime = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
    }.get(ext, "application/octet-stream")
    return send_file(path, mimetype=mime, conditional=True)


@webhooks_bp.route("/webhooks/twilio/voicemail/fallback", methods=["POST"])
def twilio_voicemail_fallback():
    """Dial action URL. Twilio calls this after the inbound <Dial> leg
    finishes — answered, no-answer, failed, or busy.

    On pickup we just hang up. On no-answer/failed/busy we play the
    tenant's greeting and then hold the line open so the already-running
    Media Stream keeps capturing audio + transcript through the voicemail.
    The offset from call start is stamped on the Call so the UI can slice
    the voicemail portion out of the full-call WAV + transcript chunks.
    """
    number_id = request.args.get("number_id", "")
    call_sid = request.form.get("CallSid", "")
    dial_status = (request.form.get("DialCallStatus") or "").lower()

    # If the human picked up, nothing more to do.
    if dial_status == "completed":
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>',
            content_type="text/xml",
        )

    pn = PhoneNumber.query.filter_by(id=number_id).first() if number_id else None
    if not pn or not pn.tenant_id:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>',
            content_type="text/xml",
        )

    # Stamp the voicemail start boundary on the Call. The media stream is
    # still running, so the audio + transcript from here on is the voicemail.
    if call_sid:
        call = Call.query.filter_by(external_id=call_sid).first()
        if call is not None:
            now = datetime.now(timezone.utc)
            started_at_ms = 0
            if call.started_at is not None:
                delta = now - call.started_at
                started_at_ms = max(0, int(delta.total_seconds() * 1000))
            if call.metadata_ is None:
                call.metadata_ = {}
            call.metadata_["voicemail"] = {
                "started_at": now.isoformat(),
                "started_at_ms": started_at_ms,
                "dial_status": dial_status,
            }
            flag_modified(call, "metadata_")
            db.session.commit()
        else:
            logger.warning(
                "Voicemail fallback for unknown call_sid=%s", call_sid
            )

    base = Config.PUBLIC_BASE_URL.rstrip("/")
    greeting_url = f"{base}/webhooks/voicemail/greeting/{pn.tenant_id}"

    greeting_path = _find_greeting_file(pn.tenant_id)
    if greeting_path:
        greeting_verb = f"<Play>{greeting_url}</Play>"
    else:
        greeting_verb = (
            "<Say>Please leave a message after the tone. "
            "When finished, hang up.</Say>"
        )

    # After the greeting, hold the line open. The Media Stream is still
    # running in parallel so we're already capturing the audio + transcript.
    # The Pause caps runaway voicemails — at timeout Twilio hangs up, which
    # fires the stream stop event and saves the WAV.
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    {greeting_verb}
    <Pause length="{Config.VOICEMAIL_MAX_LENGTH_SECONDS}"/>
    <Hangup/>
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
