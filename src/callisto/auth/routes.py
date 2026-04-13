"""Google OAuth + JWT auth endpoints."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import requests as http_requests
from flask import Blueprint, abort, g, jsonify, redirect, request

from callisto.config import Config
from callisto.extensions import db
from callisto.models import Tenant
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
    """Return current user and tenant from JWT."""
    from callisto.auth.middleware import verify_jwt
    verify_jwt()

    user = db.session.get(User, g.current_user_id)
    if not user:
        abort(401)

    tenant_data = None
    if user.tenant:
        tenant_data = {
            "id": str(user.tenant.id),
            "name": user.tenant.name,
            "slug": user.tenant.slug,
            "settings": user.tenant.settings,
        }

    return jsonify({
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "is_superadmin": user.is_superadmin,
        },
        "tenant": tenant_data,
    })
