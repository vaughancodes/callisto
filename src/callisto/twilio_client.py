"""Thin wrapper around the Twilio REST client.

Handles listing numbers on the account, syncing their SIDs into our DB,
and (re)pointing each number's voice webhook at Callisto when it is
assigned to or removed from a tenant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from callisto.config import Config

logger = logging.getLogger(__name__)


@dataclass
class TwilioNumber:
    sid: str
    e164: str
    friendly_name: str | None
    voice_url: str | None


class TwilioClientError(RuntimeError):
    """Raised when a Twilio API call fails or credentials are missing."""


@lru_cache(maxsize=1)
def _client():
    if not Config.TWILIO_ACCOUNT_SID or not Config.TWILIO_AUTH_TOKEN:
        raise TwilioClientError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set"
        )
    from twilio.rest import Client

    return Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)


def _voice_webhook_url() -> str:
    base = Config.PUBLIC_BASE_URL.rstrip("/")
    if not base:
        raise TwilioClientError(
            "PUBLIC_BASE_URL must be set to the public base URL of the "
            "Callisto deployment (e.g. https://app.callisto.works)"
        )
    return f"{base}/webhooks/twilio/voice"


def list_numbers() -> list[TwilioNumber]:
    """Fetch every IncomingPhoneNumber on the account."""
    try:
        records = _client().incoming_phone_numbers.list()
    except Exception as exc:
        raise TwilioClientError(f"Failed to list numbers: {exc}") from exc

    return [
        TwilioNumber(
            sid=r.sid,
            e164=r.phone_number,
            friendly_name=r.friendly_name,
            voice_url=r.voice_url,
        )
        for r in records
    ]


def find_number_by_e164(e164: str) -> TwilioNumber | None:
    """Look up a single number by its E.164 form."""
    try:
        records = _client().incoming_phone_numbers.list(phone_number=e164)
    except Exception as exc:
        raise TwilioClientError(f"Failed to look up {e164}: {exc}") from exc

    if not records:
        return None
    r = records[0]
    return TwilioNumber(
        sid=r.sid,
        e164=r.phone_number,
        friendly_name=r.friendly_name,
        voice_url=r.voice_url,
    )


def configure_number_for_callisto(sid: str) -> None:
    """Point a number's voice webhook at our /webhooks/twilio/voice."""
    url = _voice_webhook_url()
    try:
        _client().incoming_phone_numbers(sid).update(
            voice_url=url, voice_method="POST"
        )
        logger.info("Configured Twilio number %s -> %s", sid, url)
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to configure number {sid}: {exc}"
        ) from exc


def clear_number_voice_webhook(sid: str) -> None:
    """Clear a number's voice webhook so it stops routing to Callisto."""
    try:
        _client().incoming_phone_numbers(sid).update(
            voice_url="", voice_method="POST"
        )
        logger.info("Cleared voice webhook for Twilio number %s", sid)
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to clear webhook for {sid}: {exc}"
        ) from exc


def create_sip_domain(*, friendly_name: str, domain_name: str, tenant_id: str) -> str:
    """Create a SIP Domain on the Twilio account, wired to our voice webhook
    and configured for SIP device registration.

    domain_name should NOT include the .sip.twilio.com suffix — Twilio appends
    that automatically. tenant_id is included as a query param on the voice
    URL so the webhook can identify the owning tenant for SIP-originated calls.

    Returns the SID.
    """
    base = Config.PUBLIC_BASE_URL.rstrip("/")
    if not base:
        raise TwilioClientError(
            "PUBLIC_BASE_URL must be set to create SIP domains"
        )
    voice_url = f"{base}/webhooks/twilio/voice?tenant_id={tenant_id}"
    try:
        domain = _client().sip.domains.create(
            domain_name=f"{domain_name}.sip.twilio.com",
            friendly_name=friendly_name,
            voice_url=voice_url,
            voice_method="POST",
            sip_registration=True,
        )
        return domain.sid
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to create SIP domain {domain_name}: {exc}"
        ) from exc


def enable_sip_registration(domain_sid: str) -> None:
    """Defensive upgrade: ensure an existing SIP Domain has registration on."""
    try:
        _client().sip.domains(domain_sid).update(sip_registration=True)
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to enable SIP registration on {domain_sid}: {exc}"
        ) from exc


def delete_sip_domain(sid: str) -> None:
    try:
        _client().sip.domains(sid).delete()
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to delete SIP domain {sid}: {exc}"
        ) from exc


def create_sip_credential_list(*, friendly_name: str) -> str:
    try:
        cl = _client().sip.credential_lists.create(friendly_name=friendly_name)
        return cl.sid
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to create credential list: {exc}"
        ) from exc


def _is_already_exists(exc: Exception) -> bool:
    """Twilio returns 409 / a specific message for already-mapped credentials."""
    s = str(exc).lower()
    return "already" in s or " 409" in s or "20409" in s


def map_credential_list_for_calls(*, domain_sid: str, list_sid: str) -> None:
    """Map a credential list for INCOMING SIP call authentication."""
    try:
        _client().sip.domains(domain_sid).auth.calls.credential_list_mappings.create(
            credential_list_sid=list_sid
        )
    except Exception as exc:
        if _is_already_exists(exc):
            return
        raise TwilioClientError(
            f"Failed to map credential list {list_sid} to calls auth on domain "
            f"{domain_sid}: {exc}"
        ) from exc


def map_credential_list_for_registrations(*, domain_sid: str, list_sid: str) -> None:
    """Map a credential list for SIP device REGISTER request authentication."""
    try:
        _client().sip.domains(domain_sid).auth.registrations.credential_list_mappings.create(
            credential_list_sid=list_sid
        )
    except Exception as exc:
        if _is_already_exists(exc):
            return
        raise TwilioClientError(
            f"Failed to map credential list {list_sid} to registrations auth "
            f"on domain {domain_sid}: {exc}"
        ) from exc


def create_sip_credential(
    *, list_sid: str, username: str, password: str
) -> str:
    """Create a SIP credential. Twilio stores the password but never returns
    it again — we generate it ourselves and surface it once in the UI."""
    try:
        cred = _client().sip.credential_lists(list_sid).credentials.create(
            username=username,
            password=password,
        )
        return cred.sid
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to create SIP credential {username}: {exc}"
        ) from exc


def delete_sip_credential(*, list_sid: str, credential_sid: str) -> None:
    try:
        _client().sip.credential_lists(list_sid).credentials(credential_sid).delete()
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to delete SIP credential {credential_sid}: {exc}"
        ) from exc


def initiate_outbound_call(*, from_e164: str, to_e164: str) -> str:
    """Place an outbound call. Returns the Twilio Call SID.

    Twilio will hit our voice webhook to fetch TwiML once the call connects,
    which starts the Media Stream just like an inbound call.
    """
    url = _voice_webhook_url()
    try:
        call = _client().calls.create(
            from_=from_e164,
            to=to_e164,
            url=url,
            method="POST",
        )
        return call.sid
    except Exception as exc:
        raise TwilioClientError(
            f"Failed to initiate outbound call to {to_e164}: {exc}"
        ) from exc
