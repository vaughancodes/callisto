"""Read-only public demo API.

Backs the /demo sandbox: a recruiter or evaluator can land on /demo, pick a
seeded tenant, and walk through the real Callisto UI populated with
realistic fake data. No login, no real Twilio, no real LLM cost.

Everything here is GETs only. Mutations on the equivalent /api/v1 routes
have no demo counterpart, so the existing UI buttons for editing notes,
re-running analysis, etc. fail with 405 in demo mode and the frontend
guards them based on a simple ``isDemoMode()`` flag.

The fixture data lives in ``demo_fixtures.py`` so it can be edited
without touching this routing layer.
"""

from __future__ import annotations

import logging
import threading
import time

import requests
from flask import Blueprint, abort, jsonify, request, send_file

from callisto.config import Config

logger = logging.getLogger(__name__)

from callisto.demo_fixtures import (
    TENANTS,
    get_call,
    get_org,
    get_tenant,
    get_tenant_by_id,
    list_calls,
    list_contacts,
    list_insights,
    list_members,
    list_numbers,
    list_org_admins,
    list_org_numbers,
    list_org_tenants,
    list_summary,
    list_templates,
    list_tenants,
    list_transcript,
    list_voicemail,
    list_voicemail_transcript,
    list_voicemails,
)

demo_bp = Blueprint("demo", __name__)


# --- Auth-equivalent: tells the frontend "you're in demo mode as <slug>" ---


@demo_bp.route("/manifest", methods=["GET"])
def demo_manifest():
    """List all seeded demo tenants for the landing page picker."""
    return jsonify({"tenants": list_tenants()})


@demo_bp.route("/me", methods=["GET"])
def demo_me():
    """Stand-in for /auth/me. Resolves a synthetic user + tenant from the
    ``slug`` query param. The frontend stashes the slug in localStorage
    when the visitor enters the sandbox.
    """
    slug = (request.args.get("slug") or "").strip()
    tenant = get_tenant(slug)
    if tenant is None:
        abort(404)
    # Demo user is treated as both tenant admin and org admin so the
    # Settings pages are visible from the sandbox. Mutations are blocked
    # by the read-only guard in apiFetch and the demo blueprint exposes
    # only GET routes, so granting the admin flags is purely cosmetic.
    #
    # Memberships include every demo tenant so the sidebar's tenant
    # picker shows up. The frontend handles the actual swap entirely
    # client-side (rewrites localStorage and reloads); switchTenant()
    # never calls the backend in demo mode.
    all_memberships = [
        {
            "tenant_id": t["id"],
            "tenant_name": t["name"],
            "tenant_slug": t["slug"],
            "organization_id": t["organization_id"],
            "organization_name": t.get("organization_name"),
            "is_admin": True,
        }
        for t in TENANTS
    ]
    return jsonify({
        "user": {
            "id": "demo-user",
            "email": "demo@callisto.example",
            "name": "Demo Visitor",
            "is_superadmin": False,
        },
        "tenant": tenant,
        "is_tenant_admin": True,
        "memberships": all_memberships,
        "organization_memberships": [
            {
                "organization_id": tenant["organization_id"],
                "organization_name": tenant.get("organization_name") or "Demo Org",
                "organization_slug": "demo-org",
                "is_admin": True,
            }
        ],
    })


# --- Tenant-scoped lists used by the dashboard / pages ---


@demo_bp.route("/tenants/<tenant_id>/calls", methods=["GET"])
def calls(tenant_id):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    items = list_calls(tenant_id)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify({
        "calls": items[start:end],
        "total": len(items),
        "page": page,
        "pages": max(1, (len(items) + per_page - 1) // per_page),
    })


@demo_bp.route("/tenants/<tenant_id>/voicemails", methods=["GET"])
def voicemails(tenant_id):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    items = list_voicemails(tenant_id)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify({
        "voicemails": items[start:end],
        "total": len(items),
        "page": page,
        "pages": max(1, (len(items) + per_page - 1) // per_page),
    })


@demo_bp.route("/tenants/<tenant_id>/numbers", methods=["GET"])
def numbers(tenant_id):
    from callisto.demo_fixtures import list_numbers
    return jsonify(list_numbers(tenant_id))


@demo_bp.route("/tenants/<tenant_id>/settings", methods=["GET"])
def tenant_settings(tenant_id):
    t = get_tenant_by_id(tenant_id)
    if t is None:
        abort(404)
    return jsonify({
        "id": t["id"],
        "name": t["name"],
        "slug": t["slug"],
        "description": t["description"],
        "context": t["context"],
        "forward_to": "",
        "twilio_numbers": [],
        "audio_retention_days": 30,
        "settings": {},
    })


@demo_bp.route("/tenants/<tenant_id>/members", methods=["GET"])
def tenant_members(tenant_id):
    from callisto.demo_fixtures import list_members
    return jsonify(list_members(tenant_id))


@demo_bp.route("/tenants/<tenant_id>/voicemail/greeting", methods=["GET"])
def tenant_voicemail_greeting(tenant_id):
    return jsonify({"configured": False})


# --- Organization (read-only) ---


@demo_bp.route("/organizations/<org_id>", methods=["GET"])
def organization_detail(org_id):
    org = get_org(org_id)
    if org is None:
        abort(404)
    return jsonify(org)


@demo_bp.route("/organizations/<org_id>/tenants", methods=["GET"])
def organization_tenants(org_id):
    return jsonify(list_org_tenants(org_id))


@demo_bp.route("/organizations/<org_id>/numbers", methods=["GET"])
def organization_numbers(org_id):
    return jsonify(list_org_numbers(org_id))


@demo_bp.route("/organizations/<org_id>/admins", methods=["GET"])
def organization_admins(org_id):
    return jsonify(list_org_admins(org_id))


# --- Call-scoped detail endpoints ---


@demo_bp.route("/calls/<call_id>", methods=["GET"])
def call_detail(call_id):
    c = get_call(call_id)
    if c is None:
        abort(404)
    return jsonify(c)


@demo_bp.route("/calls/<call_id>/transcript", methods=["GET"])
def call_transcript(call_id):
    # Prefer the rebased transcript that was written alongside the TTS
    # audio — its timestamps match the rendered WAV, so the UI's
    # transcript scrubbing lines up with playback. Fall back to the
    # in-memory fixture transcript if no rebase file exists.
    from callisto.demo_audio import call_transcript_path
    path = call_transcript_path(call_id)
    if path.is_file():
        try:
            import json
            return jsonify(json.loads(path.read_text()))
        except (OSError, ValueError):
            pass
    return jsonify(list_transcript(call_id))


@demo_bp.route("/calls/<call_id>/insights", methods=["GET"])
def call_insights(call_id):
    return jsonify(list_insights(call_id))


@demo_bp.route("/calls/<call_id>/summary", methods=["GET"])
def call_summary(call_id):
    s = list_summary(call_id)
    if s is None:
        abort(404)
    return jsonify(s)


@demo_bp.route("/calls/<call_id>/voicemail", methods=["GET"])
def call_voicemail(call_id):
    vm = list_voicemail(call_id)
    if vm is None:
        abort(404)
    # Prefer rebased voicemail transcript (matches the rendered WAV's
    # timing). The renderer also captures the boundary used for rebasing
    # so the modal's started_at_ms lines up with the audio's 0:00.
    from callisto.demo_audio import voicemail_transcript_path
    path = voicemail_transcript_path(call_id)
    if path.is_file():
        try:
            import json
            payload = json.loads(path.read_text())
            return jsonify({
                **vm,
                "started_at_ms": int(
                    payload.get("rebased_started_at_ms", vm.get("started_at_ms", 0))
                ),
                "transcript": payload.get("chunks", []),
            })
        except (OSError, ValueError):
            pass
    return jsonify({**vm, "transcript": list_voicemail_transcript(call_id)})


@demo_bp.route("/calls/<call_id>/audio", methods=["GET"])
def call_audio(call_id):
    """Serve the TTS-rendered full-call WAV if it exists."""
    from callisto.demo_audio import call_audio_path
    path = call_audio_path(call_id)
    if not path.is_file():
        abort(404)
    return send_file(
        str(path),
        mimetype="audio/wav",
        as_attachment=False,
        download_name=f"call-{call_id}.wav",
        conditional=True,
    )


@demo_bp.route("/calls/<call_id>/voicemail/audio", methods=["GET"])
def call_voicemail_audio(call_id):
    """Serve the TTS-rendered voicemail-only WAV if it exists."""
    from callisto.demo_audio import voicemail_audio_path
    path = voicemail_audio_path(call_id)
    if not path.is_file():
        abort(404)
    return send_file(
        str(path),
        mimetype="audio/wav",
        as_attachment=False,
        download_name=f"voicemail-{call_id}.wav",
        conditional=True,
    )


# --- Templates / contacts (read-only browsing) ---


@demo_bp.route("/tenants/<tenant_id>/templates", methods=["GET"])
def templates(tenant_id):
    return jsonify(list_templates(tenant_id))


@demo_bp.route("/tenants/<tenant_id>/contacts", methods=["GET"])
def contacts(tenant_id):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    items = list_contacts(tenant_id)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify({
        "contacts": items[start:end],
        "total": len(items),
        "page": page,
        "pages": max(1, (len(items) + per_page - 1) // per_page),
    })


@demo_bp.route("/contacts/<contact_id>", methods=["GET"])
def contact_detail(contact_id):
    from callisto.demo_fixtures import get_contact_detail
    detail = get_contact_detail(contact_id)
    if detail is None:
        abort(404)
    return jsonify(detail)


# --- Analytics (synthetic trend data) ---


@demo_bp.route("/tenants/<tenant_id>/analytics/insights", methods=["GET"])
def analytics_insights(tenant_id):
    from callisto.demo_fixtures import get_analytics_points
    days = request.args.get("days", 30, type=int)
    return jsonify(get_analytics_points(tenant_id, days))


# --- Tenant settings stub (read-only, for the few pages that hit it) ---


@demo_bp.route("/tenants/<tenant_id>/template-categories", methods=["GET"])
def template_categories(tenant_id):
    from callisto.demo_fixtures import list_template_categories
    return jsonify(list_template_categories(tenant_id))


# --- Visit notification (ntfy.sh push to my phone) ---

# In-process rate-limit cache, keyed by client IP. Trades persistence for
# simplicity — a worker restart resets it, which is fine for this use case.
_LAST_VISIT_NOTIFY: dict[str, float] = {}
_NOTIFY_LOCK = threading.Lock()


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _send_ntfy(title: str, body: str, tags: str | None = None) -> None:
    topic = Config.NTFY_DEMO_TOPIC
    if not topic:
        return
    url = f"{Config.NTFY_BASE_URL}/{topic}"
    headers = {"Title": title}
    if tags:
        headers["Tags"] = tags
    try:
        # Tight timeout: we never want to delay the user's request waiting
        # on a third-party push service.
        requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=3)
    except requests.RequestException as exc:
        logger.warning("ntfy.sh push failed: %s", exc)


@demo_bp.route("/visit", methods=["POST"])
def demo_visit():
    """Frontend pings this once on /demo mount. We rate-limit per IP and
    fire an ntfy.sh push on each fresh visit. Always returns 204; we
    never reveal whether a notification was sent.
    """
    if not Config.NTFY_DEMO_TOPIC:
        return ("", 204)

    ip = _client_ip()
    now = time.time()
    cooldown = Config.DEMO_VISIT_NOTIFY_COOLDOWN_SECONDS

    with _NOTIFY_LOCK:
        last = _LAST_VISIT_NOTIFY.get(ip, 0.0)
        if now - last < cooldown:
            return ("", 204)
        _LAST_VISIT_NOTIFY[ip] = now
        # Periodically prune stale entries so the dict doesn't grow forever.
        if len(_LAST_VISIT_NOTIFY) > 1000:
            cutoff = now - max(cooldown * 4, 3600)
            for stale_ip in [k for k, v in _LAST_VISIT_NOTIFY.items() if v < cutoff]:
                _LAST_VISIT_NOTIFY.pop(stale_ip, None)

    referrer = request.headers.get("Referer") or "direct"
    user_agent = request.headers.get("User-Agent", "")[:200]
    body_text = (
        f"IP: {ip}\n"
        f"Referrer: {referrer}\n"
        f"UA: {user_agent}"
    )
    _send_ntfy(
        title="Callisto demo visited",
        body=body_text,
        tags="eyes",
    )
    return ("", 204)
