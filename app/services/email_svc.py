"""Email service using Mailpit (local SMTP) for development.

Fire-and-forget: email failures are logged but never raised. The public
submission endpoint must succeed even if email is down — this is the
"safe side effects" requirement.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_notification(
    to_addr: str,
    subject: str,
    body: str,
) -> bool:
    """Send a plain-text email via SMTP (Mailpit in dev).

    Returns True on success, False on failure. Never raises.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.email_from
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.email_from, [to_addr], msg.as_string())

        logger.info("Email sent to %s: %s", to_addr, subject)
        return True
    except Exception as exc:
        logger.warning("Email send failed (to=%s): %s — submission will still succeed", to_addr, exc)
        return False
