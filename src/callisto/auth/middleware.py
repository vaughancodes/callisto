"""JWT verification middleware."""

import jwt as pyjwt
from flask import abort, g, request

from callisto.config import Config


def verify_jwt():
    """Extract and verify JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(401, description="Missing or invalid Authorization header")

    token = auth_header[7:]
    try:
        payload = pyjwt.decode(
            token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM]
        )
    except pyjwt.ExpiredSignatureError:
        abort(401, description="Token expired")
    except pyjwt.InvalidTokenError:
        abort(401, description="Invalid token")

    g.current_user_id = payload["user_id"]
    g.tenant_id = payload.get("tenant_id")
    g.is_superadmin = payload.get("is_superadmin", False)


def require_superadmin():
    """Abort 403 if the current user is not a superadmin."""
    verify_jwt()
    if not g.is_superadmin:
        abort(403, description="Superadmin access required")
