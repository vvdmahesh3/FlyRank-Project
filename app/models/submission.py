"""Submission model.

A Submission is a single form entry from a visitor on a tenant's website.
It stores the raw form data, enriched geo/IP data, and a status field for
moderation workflows.

The `submitter_ip` is captured server-side (never trusted from the client)
and used for rate limiting and geo enrichment.
"""

import uuid

from sqlalchemy import String, ForeignKey, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Submission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "submissions"

    widget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("widgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Raw form data as submitted by the visitor (validated against widget fields_config)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Server-captured metadata
    submitter_ip: Mapped[str | None] = mapped_column(INET, nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Geo enrichment (nullable — stored without geo if both providers fail)
    geo_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_lat: Mapped[float | None] = mapped_column(nullable=True)
    geo_lon: Mapped[float | None] = mapped_column(nullable=True)
    geo_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Spam / moderation status: "new", "flagged", "approved", "rejected"
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)
    spam_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    widget: Mapped["Widget"] = relationship("Widget", back_populates="submissions")
