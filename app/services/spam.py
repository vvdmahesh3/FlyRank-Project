"""Spam protection: honeypot detection and basic heuristics.

The honeypot is a hidden field (`website_url`) that real visitors never
see or fill. If it contains a value, the submission is almost certainly
from a bot that blindly fills all fields.

We also compute a simple spam_score (0 = clean, higher = suspicious) based
on honeypot hits and timing. This is intentionally lightweight — the
rate limiter is the primary defense against volume attacks.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def check_honeypot(honeypot_value: Optional[str]) -> bool:
    """Return True if the honeypot was triggered (spam detected)."""
    if honeypot_value and honeypot_value.strip():
        logger.info("Honeypot triggered: bot detected")
        return True
    return False


def compute_spam_score(
    honeypot_triggered: bool,
    submitter_ip: Optional[str] = None,
) -> int:
    """Return a spam score 0-100. Higher = more suspicious."""
    score = 0
    if honeypot_triggered:
        score += 100
    return min(score, 100)
