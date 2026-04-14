from flask import Blueprint

bp = Blueprint("api", __name__)


@bp.before_request
def require_jwt():
    """Protect all /api/v1/* routes with JWT authentication."""
    from callisto.auth.middleware import verify_jwt
    verify_jwt()


from callisto.api import (  # noqa: E402, F401
    analytics,
    calls,
    contacts,
    google_sync,
    organizations,
    templates,
    tenant_settings,
    tenants,
)
