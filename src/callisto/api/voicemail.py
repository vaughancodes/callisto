"""Voicemail greeting management.

The uploaded greeting is stored on local disk (one file per tenant, named by
tenant id + original extension). Metadata about the file lives in
``tenant.settings["voicemail_greeting"]``. Twilio fetches the audio via the
public ``/webhooks/voicemail/greeting/<tenant_id>`` endpoint (see
``callisto.api.webhooks``); this module only handles the authenticated
upload/delete/read side.
"""

import os

from flask import current_app, jsonify, request
from sqlalchemy.orm.attributes import flag_modified

from callisto.api import bp
from callisto.auth.middleware import require_tenant_admin
from callisto.config import Config
from callisto.extensions import db
from callisto.models import Tenant


ALLOWED_EXTENSIONS = {"mp3", "wav"}
ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
}


def _greeting_dir() -> str:
    path = Config.VOICEMAIL_GREETINGS_DIR
    os.makedirs(path, exist_ok=True)
    return path


def _greeting_path(tenant_id, extension: str) -> str:
    return os.path.join(_greeting_dir(), f"{tenant_id}.{extension}")


def _existing_greeting_files(tenant_id) -> list[str]:
    d = _greeting_dir()
    prefix = f"{tenant_id}."
    return [
        os.path.join(d, f) for f in os.listdir(d) if f.startswith(prefix)
    ]


def _serialize_greeting(tenant: Tenant) -> dict:
    g = (tenant.settings or {}).get("voicemail_greeting") or {}
    if not g:
        return {"configured": False}
    return {
        "configured": True,
        "filename": g.get("filename"),
        "content_type": g.get("content_type"),
        "size_bytes": g.get("size_bytes"),
        "uploaded_at": g.get("uploaded_at"),
    }


@bp.route("/tenants/<uuid:tenant_id>/voicemail/greeting", methods=["GET"])
def get_voicemail_greeting(tenant_id):
    require_tenant_admin(tenant_id)
    tenant = db.get_or_404(Tenant, tenant_id)
    return jsonify(_serialize_greeting(tenant))


@bp.route("/tenants/<uuid:tenant_id>/voicemail/greeting", methods=["POST"])
def upload_voicemail_greeting(tenant_id):
    require_tenant_admin(tenant_id)
    tenant = db.get_or_404(Tenant, tenant_id)

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": "No file uploaded. Use form field 'file'."}), 400

    ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": f"Unsupported extension .{ext}. Upload mp3 or wav.",
        }), 400

    if upload.mimetype and upload.mimetype not in ALLOWED_CONTENT_TYPES:
        return jsonify({
            "error": f"Unsupported content type {upload.mimetype}.",
        }), 400

    data = upload.read()
    if len(data) == 0:
        return jsonify({"error": "Uploaded file is empty."}), 400
    if len(data) > Config.VOICEMAIL_MAX_UPLOAD_BYTES:
        return jsonify({
            "error": f"File exceeds {Config.VOICEMAIL_MAX_UPLOAD_BYTES} bytes.",
        }), 413

    # Replace any prior greeting for this tenant regardless of extension.
    for stale in _existing_greeting_files(tenant_id):
        try:
            os.remove(stale)
        except OSError:
            current_app.logger.warning("Could not remove old greeting %s", stale)

    target = _greeting_path(tenant_id, ext)
    with open(target, "wb") as f:
        f.write(data)

    from datetime import datetime, timezone

    if tenant.settings is None:
        tenant.settings = {}
    tenant.settings["voicemail_greeting"] = {
        "filename": upload.filename,
        "extension": ext,
        "content_type": upload.mimetype or f"audio/{ext}",
        "size_bytes": len(data),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    flag_modified(tenant, "settings")
    db.session.commit()

    return jsonify(_serialize_greeting(tenant)), 201


@bp.route("/tenants/<uuid:tenant_id>/voicemail/greeting", methods=["DELETE"])
def delete_voicemail_greeting(tenant_id):
    require_tenant_admin(tenant_id)
    tenant = db.get_or_404(Tenant, tenant_id)

    for stale in _existing_greeting_files(tenant_id):
        try:
            os.remove(stale)
        except OSError:
            current_app.logger.warning("Could not remove greeting %s", stale)

    if tenant.settings and "voicemail_greeting" in tenant.settings:
        tenant.settings.pop("voicemail_greeting", None)
        flag_modified(tenant, "settings")
        db.session.commit()

    return "", 204
