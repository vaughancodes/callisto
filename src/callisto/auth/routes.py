"""Google OAuth + JWT auth endpoints."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import requests as http_requests
from flask import Blueprint, abort, g, jsonify, redirect, request

from callisto.config import Config
from callisto.extensions import db
from callisto.models import (
    Organization,
    OrganizationMembership,
    Tenant,
    TenantMembership,
)
from callisto.models.user import User

auth_bp = Blueprint("auth", __name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _issue_jwt(user: User) -> str:
    payload = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "email": user.email,
        "is_superadmin": user.is_superadmin,
        "exp": datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


@auth_bp.route("/auth/google/login")
def google_login():
    """Redirect to Google OAuth consent screen."""
    params = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "redirect_uri": Config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile https://www.googleapis.com/auth/contacts.readonly",
        "access_type": "offline",
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(f"{GOOGLE_AUTH_URL}?{query}")


@auth_bp.route("/auth/google/callback")
def google_callback():
    """Handle Google OAuth callback — exchange code, find/create user, issue JWT."""
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing authorization code"}), 400

    # Exchange code for tokens
    token_resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": Config.GOOGLE_CLIENT_ID,
        "client_secret": Config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": Config.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=10)

    if token_resp.status_code != 200:
        return jsonify({"error": "Token exchange failed"}), 400

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    # Get user info from Google
    userinfo_resp = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        return jsonify({"error": "Failed to fetch user info"}), 400

    userinfo = userinfo_resp.json()
    google_id = userinfo["sub"]
    email = userinfo["email"]
    name = userinfo.get("name", email.split("@")[0])

    # Find or create user
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        is_superadmin = email in Config.SUPERADMIN_EMAILS
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            is_superadmin=is_superadmin,
            tenant_id=None,  # Superadmin assigns tenant later
        )
        db.session.add(user)
        db.session.commit()

    token = _issue_jwt(user)

    # Redirect to frontend with token + Google access token (for contacts sync)
    frontend_url = Config.FRONTEND_URL.rstrip("/")
    return redirect(
        f"{frontend_url}/auth/callback?token={token}&google_token={access_token}"
    )


def _accessible_tenants(user: User) -> list[Tenant]:
    """Tenants the user can read: superadmin → all; otherwise direct
    memberships ∪ tenants of orgs the user belongs to."""
    if user.is_superadmin:
        return Tenant.query.order_by(Tenant.name).all()

    direct_ids = {
        m.tenant_id for m in TenantMembership.query.filter_by(user_id=user.id).all()
    }
    org_ids = [
        m.organization_id
        for m in OrganizationMembership.query.filter_by(user_id=user.id).all()
    ]
    if org_ids:
        for t in Tenant.query.filter(Tenant.organization_id.in_(org_ids)).all():
            direct_ids.add(t.id)

    if not direct_ids:
        return []
    return (
        Tenant.query.filter(Tenant.id.in_(direct_ids)).order_by(Tenant.name).all()
    )


def _is_org_admin(user: User, org_id) -> bool:
    if user.is_superadmin:
        return True
    return (
        OrganizationMembership.query.filter_by(
            user_id=user.id, organization_id=org_id, is_admin=True
        ).first()
        is not None
    )


def _is_tenant_admin(user: User, tenant: Tenant) -> bool:
    if user.is_superadmin:
        return True
    if _is_org_admin(user, tenant.organization_id):
        return True
    m = TenantMembership.query.filter_by(
        user_id=user.id, tenant_id=tenant.id, is_admin=True
    ).first()
    return m is not None


@auth_bp.route("/auth/me")
def auth_me():
    """Return current user, active tenant, all tenant + org memberships,
    and effective role flags so the frontend can branch UI off them."""
    from callisto.auth.middleware import verify_jwt
    verify_jwt()

    user = db.session.get(User, g.current_user_id)
    if not user:
        abort(401)

    accessible = _accessible_tenants(user)
    accessible_ids = {t.id for t in accessible}

    # Active tenant (from user.tenant_id) — fall back to first accessible if
    # the stored one is no longer reachable.
    tenant_data = None
    is_tenant_admin = False
    active_tenant = user.tenant
    if active_tenant and active_tenant.id not in accessible_ids:
        active_tenant = None
        user.tenant_id = None
        db.session.commit()
    if not active_tenant and accessible:
        active_tenant = accessible[0]
        user.tenant_id = active_tenant.id
        db.session.commit()

    if active_tenant:
        tenant_data = {
            "id": str(active_tenant.id),
            "name": active_tenant.name,
            "slug": active_tenant.slug,
            "description": active_tenant.description,
            "organization_id": str(active_tenant.organization_id),
            "settings": active_tenant.settings,
        }
        is_tenant_admin = _is_tenant_admin(user, active_tenant)

    # Memberships list (each tenant the user can switch to)
    memberships = []
    for t in accessible:
        memberships.append({
            "tenant_id": str(t.id),
            "tenant_name": t.name,
            "tenant_slug": t.slug,
            "organization_id": str(t.organization_id),
            "organization_name": t.organization.name if t.organization else None,
            "is_admin": _is_tenant_admin(user, t),
        })

    # Organization memberships (so the frontend can show org-admin UI)
    if user.is_superadmin:
        orgs = Organization.query.order_by(Organization.name).all()
        org_memberships = [
            {
                "organization_id": str(o.id),
                "organization_name": o.name,
                "organization_slug": o.slug,
                "is_admin": True,
            }
            for o in orgs
        ]
    else:
        org_memberships = [
            {
                "organization_id": str(m.organization_id),
                "organization_name": m.organization.name,
                "organization_slug": m.organization.slug,
                "is_admin": m.is_admin,
            }
            for m in OrganizationMembership.query.filter_by(user_id=user.id).all()
        ]

    return jsonify({
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "is_superadmin": user.is_superadmin,
        },
        "tenant": tenant_data,
        "is_tenant_admin": is_tenant_admin,
        "memberships": memberships,
        "organization_memberships": org_memberships,
    })


@auth_bp.route("/auth/switch-tenant", methods=["POST"])
def switch_tenant():
    """Switch the user's active tenant. Returns a new JWT."""
    from callisto.auth.middleware import verify_jwt
    verify_jwt()

    data = request.get_json() or {}
    new_tenant_id = data.get("tenant_id")
    if not new_tenant_id:
        return jsonify({"error": "tenant_id is required"}), 400

    user = db.session.get(User, g.current_user_id)
    if not user:
        abort(401)

    # Verify tenant exists. Use filter_by so the string→UUID coercion
    # happens (db.session.get with a string PK on UUID columns returns None).
    tenant = Tenant.query.filter_by(id=new_tenant_id).first()
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    # Verify the user has access (direct membership, org membership, or superadmin)
    if not user.is_superadmin:
        direct = TenantMembership.query.filter_by(
            user_id=user.id, tenant_id=new_tenant_id
        ).first()
        org_member = OrganizationMembership.query.filter_by(
            user_id=user.id, organization_id=tenant.organization_id
        ).first()
        if not direct and not org_member:
            return jsonify({"error": "Not a member of this tenant"}), 403

    user.tenant_id = tenant.id
    db.session.commit()

    new_token = _issue_jwt(user)
    return jsonify({"token": new_token})
