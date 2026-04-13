"""Google Contacts sync endpoint + Celery task."""

import logging

import requests as http_requests
from flask import g, jsonify, request

from callisto.api import bp
from callisto.api.contacts import _normalize_phone
from callisto.extensions import db
from callisto.models.contact import Contact
from callisto.models.user import User

logger = logging.getLogger(__name__)


@bp.route("/contacts/sync/google", methods=["POST"])
def trigger_google_sync():
    """Trigger a Google Contacts sync for the current user's tenant.

    Expects the Google access token in the request body (the frontend
    stores it after OAuth login and sends it here).
    """
    data = request.get_json() or {}
    access_token = data.get("access_token")

    if not access_token:
        return jsonify({"error": "access_token is required"}), 400

    user = db.session.get(User, g.current_user_id)
    if not user or not user.tenant_id:
        return jsonify({"error": "No tenant assigned"}), 400

    # Run synchronously for MVP — could move to Celery task for large contact lists
    result = _sync_google_contacts(str(user.tenant_id), access_token)

    # Backfill contacts on existing calls
    from callisto.api.contacts import _backfill_contacts
    result["calls_matched"] = _backfill_contacts(str(user.tenant_id))

    return jsonify(result)


def _sync_google_contacts(tenant_id: str, access_token: str) -> dict:
    """Pull contacts from Google People API and upsert into the database."""
    url = "https://people.googleapis.com/v1/people/me/connections"
    params = {
        "personFields": "names,phoneNumbers,emailAddresses,organizations",
        "pageSize": 1000,
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    created = 0
    updated = 0
    total = 0

    # Build existing contact lookup by google_contact_id and phone
    existing = Contact.query.filter_by(tenant_id=tenant_id).all()
    gid_map: dict[str, Contact] = {}
    phone_map: dict[str, Contact] = {}
    for c in existing:
        if c.google_contact_id:
            gid_map[c.google_contact_id] = c
        for p in (c.phone_numbers or []):
            phone_map[p] = c

    while url:
        resp = http_requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.error("Google People API error: %s %s", resp.status_code, resp.text[:200])
            break

        data = resp.json()
        connections = data.get("connections", [])

        for person in connections:
            resource_name = person.get("resourceName", "")
            names = person.get("names", [])
            phones = person.get("phoneNumbers", [])
            emails = person.get("emailAddresses", [])
            orgs = person.get("organizations", [])

            # Skip contacts without phone numbers
            if not phones:
                continue

            name = names[0].get("displayName", "Unknown") if names else "Unknown"
            company = orgs[0].get("name") if orgs else None
            email = emails[0].get("value") if emails else None

            normalized_phones = []
            for ph in phones:
                p = _normalize_phone(ph.get("canonicalForm") or ph.get("value", ""))
                if p:
                    normalized_phones.append(p)

            if not normalized_phones:
                continue

            total += 1

            # Upsert: first by google_contact_id, then by phone
            contact = gid_map.get(resource_name)
            if not contact:
                for p in normalized_phones:
                    if p in phone_map:
                        contact = phone_map[p]
                        break

            if contact:
                contact.name = name
                if company:
                    contact.company = company
                if email:
                    contact.email = email
                contact.google_contact_id = resource_name
                # Merge phone numbers
                existing_phones = set(contact.phone_numbers or [])
                existing_phones.update(normalized_phones)
                contact.phone_numbers = list(existing_phones)
                updated += 1
            else:
                contact = Contact(
                    tenant_id=tenant_id,
                    name=name,
                    company=company,
                    phone_numbers=normalized_phones,
                    email=email,
                    google_contact_id=resource_name,
                )
                db.session.add(contact)
                gid_map[resource_name] = contact
                for p in normalized_phones:
                    phone_map[p] = contact
                created += 1

        # Handle pagination
        next_token = data.get("nextPageToken")
        if next_token:
            params["pageToken"] = next_token
        else:
            url = None

    db.session.commit()
    logger.info(
        "Google sync for tenant %s: %d contacts processed, %d created, %d updated",
        tenant_id, total, created, updated,
    )
    return {"total": total, "created": created, "updated": updated}
