"""Google OAuth + JWT auth endpoints."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import requests as http_requests
from flask import Blueprint, abort, g, jsonify, redirect, request

from callisto.config import Config
from callisto.extensions import db
from callisto.models import Tenant, TenantMembership
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


@auth_bp.route("/auth/me")
def auth_me():
    """Return current user, active tenant, and all tenant memberships."""
    from callisto.auth.middleware import verify_jwt
    verify_jwt()

    user = db.session.get(User, g.current_user_id)
    if not user:
        abort(401)

    # Active tenant (from user.tenant_id)
    tenant_data = None
    is_tenant_admin = False
    if user.tenant:
        tenant_data = {
            "id": str(user.tenant.id),
            "name": user.tenant.name,
            "slug": user.tenant.slug,
            "description": user.tenant.description,
            "settings": user.tenant.settings,
        }
        # Check if user is admin of current tenant
        if user.is_superadmin:
            is_tenant_admin = True
        else:
            m = TenantMembership.query.filter_by(
                user_id=user.id, tenant_id=user.tenant_id, is_admin=True
            ).first()
            is_tenant_admin = m is not None

    # All memberships (tenants the user can access)
    if user.is_superadmin:
        tenants = Tenant.query.order_by(Tenant.name).all()
        memberships = [
            {
                "tenant_id": str(t.id),
                "tenant_name": t.name,
                "tenant_slug": t.slug,
                "is_admin": True,
            }
            for t in tenants
        ]
    else:
        memberships_query = (
            TenantMembership.query.filter_by(user_id=user.id).all()
        )
        memberships = [
            {
                "tenant_id": str(m.tenant_id),
                "tenant_name": m.tenant.name,
                "tenant_slug": m.tenant.slug,
                "is_admin": m.is_admin,
            }
            for m in memberships_query
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

    # Verify the user has membership (or is superadmin)
    if not user.is_superadmin:
        membership = TenantMembership.query.filter_by(
            user_id=user.id, tenant_id=new_tenant_id
        ).first()
        if not membership:
            return jsonify({"error": "Not a member of this tenant"}), 403

    # Verify tenant exists
    tenant = db.session.get(Tenant, new_tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    user.tenant_id = tenant.id
    db.session.commit()

    new_token = _issue_jwt(user)
    return jsonify({"token": new_token})
