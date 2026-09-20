"""Widget model.

A Widget is a configurable form that a tenant embeds on their site. Each
widget has a unique public_id used in the embed snippet and the public
submission endpoint — this is NOT the primary key (UUID), so the internal
ID is never exposed to the public internet.

The `allowed_origins` list drives the per-widget CORS policy on the public
submission endpoint. Only origins the tenant explicitly allows can POST.
"""

import uuid
from typing import List

from sqlalchemy import String, ForeignKey, Text, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Widget(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "widgets"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Widget type: "contact_form", "newsletter", "lead_capture", "survey"
    widget_type: Mapped[str] = mapped_column(String(50), default="contact_form", nullable=False)

    # JSON schema of fields the widget collects (name, email, phone, message, etc.)
    fields_config: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)

    # Comma-separated list of allowed origins for CORS on public submissions
    allowed_origins: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )

    # Optional webhook URL (per-tenant side effect)
    webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Email notification recipients (comma-separated in the stored string)
    notify_email: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Version for cache-busting the delivered JS bundle
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="widgets")
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="widget", cascade="all, delete-orphan"
    )
