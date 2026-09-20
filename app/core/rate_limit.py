"""SlowAPI rate limiter configuration.

Two limiters:
- **Dashboard/auth API**: per-IP, generous (default 60/min).
- **Public submission**: per-IP+widget, strict (default 10/min) to prevent
  abuse from the open internet.

Rate limiting is enforced *before* the request reaches the database so a
burst of spam cannot exhaust the connection pool.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _public_key_func(request) -> str:
    """Key by IP + widget_id so limits are per-widget, not global."""
    widget_id = request.path_params.get("widget_id", "unknown")
    return f"{get_remote_address(request)}:{widget_id}"


limiter = Limiter(key_func=get_remote_address)
public_limiter = Limiter(key_func=_public_key_func)
