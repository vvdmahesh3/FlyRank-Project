"""Webhook service — fire-and-forget HTTP POST to a tenant-configured URL.

Like email, webhook failures are logged but never block submission success.
The timeout is short (default 5s) so a slow/unresponsive webhook endpoint
cannot stall the public submission path.
"""

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def fire_webhook(url: str, payload: dict[str, Any]) -> bool:
    """POST the submission payload to the webhook URL.

    Returns True on success (2xx), False otherwise. Never raises.
    """
    try:
        resp = httpx.post(
            url,
            json=payload,
            timeout=settings.webhook_timeout_seconds,
        )
        if 200 <= resp.status_code < 300:
            logger.info("Webhook delivered to %s (status %s)", url, resp.status_code)
            return True
        logger.warning("Webhook to %s returned %s", url, resp.status_code)
        return False
    except Exception as exc:
        logger.warning("Webhook delivery failed (url=%s): %s — submission will still succeed", url, exc)
        return False
