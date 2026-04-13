"""Contacts CRUD API + CSV import."""

import csv
import io
import re

from flask import g, jsonify, request

from callisto.api import bp
from callisto.extensions import db
from callisto.models.contact import Contact


def _normalize_phone(raw: str) -> str | None:
    """Normalize a phone number to E.164 format. Returns None if unparseable."""
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if not digits:
        return None
    # If it starts with +, keep as-is (already E.164)
    if digits.startswith("+"):
        return digits if len(digits) >= 8 else None
    # If 10 digits, assume US/CA and prepend +1
    if len(digits) == 10:
        return f"+1{digits}"
    # If 11 digits starting with 1, prepend +
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    # Otherwise prepend + and hope for the best
    if len(digits) >= 8:
        return f"+{digits}"
    return None


def _serialize_contact(c: Contact) -> dict:
    return {
        "id": str(c.id),
        "tenant_id": str(c.tenant_id),
        "name": c.name,
        "company": c.company,
        "phone_numbers": c.phone_numbers,
        "email": c.email,
        "google_contact_id": c.google_contact_id,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def lookup_contact_by_phone(tenant_id: str, phone: str) -> Contact | None:
    """Find a contact by phone number for a given tenant."""
    import logging
    logger = logging.getLogger(__name__)

    normalized = _normalize_phone(phone)
    if not normalized:
        logger.debug("Contact lookup: could not normalize phone '%s'", phone)
        return None

    contacts = Contact.query.filter_by(tenant_id=tenant_id).all()
    logger.info("Contact lookup: searching %d contacts for %s (tenant=%s)",
                len(contacts), normalized, tenant_id)
    for c in contacts:
        phones = c.phone_numbers or []
        if normalized in phones:
            return c
        # Also try without +1 prefix vs with (handle format mismatches)
        for p in phones:
            norm_p = _normalize_phone(p)
            if norm_p and norm_p == normalized:
                return c
    return None


# --- CRUD ---

@bp.route("/tenants/<uuid:tenant_id>/contacts", methods=["GET"])
def list_contacts(tenant_id):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("q", "").strip()

    query = Contact.query.filter_by(tenant_id=tenant_id)
    if search:
        query = query.filter(
            db.or_(
                Contact.name.ilike(f"%{search}%"),
                Contact.company.ilike(f"%{search}%"),
                Contact.email.ilike(f"%{search}%"),
            )
        )

    pagination = query.order_by(Contact.name).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "contacts": [_serialize_contact(c) for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })


@bp.route("/tenants/<uuid:tenant_id>/contacts", methods=["POST"])
def create_contact(tenant_id):
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    # Normalize phone numbers
    raw_phones = data.get("phone_numbers", [])
    phones = [p for p in (_normalize_phone(r) for r in raw_phones) if p]

    contact = Contact(
        tenant_id=tenant_id,
        name=data["name"],
        company=data.get("company"),
        phone_numbers=phones,
        email=data.get("email"),
        metadata_=data.get("metadata", {}),
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify(_serialize_contact(contact)), 201


@bp.route("/contacts/<uuid:contact_id>", methods=["GET"])
def get_contact(contact_id):
    from callisto.models import Call, CallSummary

    contact = db.get_or_404(Contact, contact_id)
    data = _serialize_contact(contact)

    # Include calls for this contact
    calls = (
        Call.query
        .filter_by(contact_id=contact.id)
        .order_by(Call.started_at.desc())
        .all()
    )
    data["calls"] = [
        {
            "id": str(c.id),
            "direction": c.direction,
            "caller_number": c.caller_number,
            "status": c.status,
            "started_at": c.started_at.isoformat() if c.started_at else None,
            "ended_at": c.ended_at.isoformat() if c.ended_at else None,
            "duration_sec": c.duration_sec,
            "notes": c.notes,
            "topics": (c.summary.key_topics[:3] if c.summary and c.summary.key_topics else []),
            "sentiment": c.summary.sentiment if c.summary else None,
            "summary_text": c.summary.summary if c.summary else None,
        }
        for c in calls
    ]

    # Sentiment summary from call summaries
    call_ids = [c.id for c in calls]
    summaries = (
        CallSummary.query
        .filter(CallSummary.call_id.in_(call_ids))
        .order_by(CallSummary.created_at.desc())
        .all()
    ) if call_ids else []

    sentiment_counts: dict[str, int] = {}
    for s in summaries:
        sentiment_counts[s.sentiment] = sentiment_counts.get(s.sentiment, 0) + 1

    data["sentiment_summary"] = {
        "counts": sentiment_counts,
        "latest": summaries[0].sentiment if summaries else None,
        "total_calls": len(calls),
        "analyzed_calls": len(summaries),
    }

    # Collect all key topics across summaries
    topic_counts: dict[str, int] = {}
    for s in summaries:
        for topic in (s.key_topics or []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    data["top_topics"] = sorted(topic_counts.items(), key=lambda x: -x[1])[:10]

    return jsonify(data)


@bp.route("/contacts/<uuid:contact_id>", methods=["PUT"])
def update_contact(contact_id):
    contact = db.get_or_404(Contact, contact_id)
    data = request.get_json()

    if "name" in data:
        contact.name = data["name"]
    if "company" in data:
        contact.company = data["company"]
    if "phone_numbers" in data:
        contact.phone_numbers = [
            p for p in (_normalize_phone(r) for r in data["phone_numbers"]) if p
        ]
    if "email" in data:
        contact.email = data["email"]
    if "notes" in data:
        contact.notes = data["notes"]
    if "metadata" in data:
        contact.metadata_ = data["metadata"]

    db.session.commit()
    return jsonify(_serialize_contact(contact))


@bp.route("/contacts/<uuid:contact_id>/notes", methods=["PUT"])
def update_contact_notes(contact_id):
    contact = db.get_or_404(Contact, contact_id)
    data = request.get_json()
    contact.notes = data.get("notes", "")
    db.session.commit()
    return jsonify({"notes": contact.notes})


@bp.route("/contacts/<uuid:contact_id>", methods=["DELETE"])
def delete_contact(contact_id):
    contact = db.get_or_404(Contact, contact_id)
    db.session.delete(contact)
    db.session.commit()
    return "", 204


# --- Backfill contacts on existing calls ---

def _backfill_contacts(tenant_id) -> int:
    """Match unmatched calls against contacts by phone number. Returns count matched."""
    from callisto.models import Call

    contacts = Contact.query.filter_by(tenant_id=tenant_id).all()
    phone_to_contact: dict[str, Contact] = {}
    for c in contacts:
        for p in (c.phone_numbers or []):
            phone_to_contact[p] = c

    calls = Call.query.filter_by(tenant_id=tenant_id, contact_id=None).all()
    matched = 0
    for call in calls:
        normalized = _normalize_phone(call.caller_number)
        if normalized and normalized in phone_to_contact:
            call.contact_id = phone_to_contact[normalized].id
            matched += 1

    db.session.commit()
    return matched


@bp.route("/tenants/<uuid:tenant_id>/contacts/backfill", methods=["POST"])
def backfill_call_contacts(tenant_id):
    """Match existing calls against contacts by phone number."""
    matched = _backfill_contacts(str(tenant_id))
    return jsonify({"matched": matched})


# --- CSV Import ---

@bp.route("/tenants/<uuid:tenant_id>/contacts/import", methods=["POST"])
def import_contacts_csv(tenant_id):
    """Import contacts from a CSV file.

    Expects multipart form with:
      - file: the CSV file
      - name_col: column name for contact name (default: "name")
      - company_col: column name for company (default: "company")
      - phone_col: column name for phone number (default: "phone")
      - email_col: column name for email (default: "email")

    Upserts on phone number — if a contact with the same phone already exists
    for this tenant, it updates instead of creating a duplicate.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    name_col = request.form.get("name_col", "name")
    company_col = request.form.get("company_col", "company")
    phone_col = request.form.get("phone_col", "phone")
    email_col = request.form.get("email_col", "email")

    content = file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    created = 0
    updated = 0
    skipped = 0

    # Build a lookup of existing contacts by phone for this tenant
    existing = Contact.query.filter_by(tenant_id=tenant_id).all()
    phone_to_contact: dict[str, Contact] = {}
    for c in existing:
        for p in (c.phone_numbers or []):
            phone_to_contact[p] = c

    for row in reader:
        name = row.get(name_col, "").strip()
        if not name:
            skipped += 1
            continue

        raw_phone = row.get(phone_col, "").strip()
        phone = _normalize_phone(raw_phone) if raw_phone else None
        company = row.get(company_col, "").strip() or None
        email = row.get(email_col, "").strip() or None

        # Upsert on phone number
        if phone and phone in phone_to_contact:
            contact = phone_to_contact[phone]
            contact.name = name
            if company:
                contact.company = company
            if email:
                contact.email = email
            updated += 1
        else:
            phones = [phone] if phone else []
            contact = Contact(
                tenant_id=tenant_id,
                name=name,
                company=company,
                phone_numbers=phones,
                email=email,
            )
            db.session.add(contact)
            if phone:
                phone_to_contact[phone] = contact
            created += 1

    db.session.commit()
    matched = _backfill_contacts(str(tenant_id))
    return jsonify({
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "calls_matched": matched,
    })
