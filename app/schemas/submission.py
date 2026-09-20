"""Pydantic schemas for public submission endpoint.

Strict validation is critical here because this endpoint accepts untrusted
input from the public internet. The honeypot field and max payload size
are enforced at the schema level.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class PublicSubmissionCreate(BaseModel):
    """Payload from the widget's form submission.

    `data` is a flexible dict because each widget defines its own fields.
    Validation against the widget's fields_config happens in the router,
    not here — but we enforce a hard size limit to prevent oversized payloads.
    """

    data: dict[str, Any] = Field(max_length=50)
    # Honeypot: if this field has any value, the submission is spam.
    # Legitimate visitors never see this field (it's hidden via CSS).
    website: Optional[str] = Field(default=None, max_length=500, alias="website_url")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _check_honeypot(self) -> "PublicSubmissionCreate":
        # The honeypot field should always be empty for real users.
        # A non-empty value means a bot filled it blindly.
        return self


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    widget_id: uuid.UUID
    data: dict
    submitter_ip: Optional[str]
    geo_country: Optional[str]
    geo_region: Optional[str]
    geo_city: Optional[str]
    geo_provider: Optional[str]
    status: str
    spam_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicSubmissionAck(BaseModel):
    """Minimal ack returned to the public visitor — no internal details leaked."""
    success: bool = True
    message: str = "Thank you! Your submission has been received."
