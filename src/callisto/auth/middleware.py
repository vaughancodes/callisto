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


def require_tenant_admin(tenant_id: str):
    """Abort 403 if the current user is not an admin of the given tenant.
    Superadmins always pass.
    """
    from callisto.models import TenantMembership

    if g.is_superadmin:
        return

    membership = TenantMembership.query.filter_by(
        user_id=g.current_user_id, tenant_id=str(tenant_id), is_admin=True
    ).first()
    if not membership:
        abort(403, description="Tenant admin access required")


def is_tenant_member(tenant_id: str) -> bool:
    """Return True if the current user is a member of the given tenant (or superadmin)."""
    from callisto.models import TenantMembership

    if g.is_superadmin:
        return True

    return (
        TenantMembership.query.filter_by(
            user_id=g.current_user_id, tenant_id=str(tenant_id)
        ).first()
        is not None
    )
