"""Pydantic schemas for widget CRUD and snippet generation."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class FieldDefinition(BaseModel):
    """A single form field in the widget's fields_config."""
    name: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=50)  # text, email, tel, textarea, select
    required: bool = False
    placeholder: Optional[str] = Field(default=None, max_length=200)
    options: Optional[List[str]] = None  # for select fields

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        allowed = {"text", "email", "tel", "textarea", "select", "number", "url"}
        if v not in allowed:
            raise ValueError(f"Field type must be one of {allowed}")
        return v


class WidgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    widget_type: str = Field(default="contact_form", max_length=50)
    fields_config: List[FieldDefinition] = Field(default_factory=list, max_length=20)
    allowed_origins: List[str] = Field(default_factory=list, max_length=20)
    webhook_url: Optional[str] = Field(default=None, max_length=2048)
    notify_email: Optional[str] = Field(default=None, max_length=512)

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origins(cls, origins: List[str]) -> List[str]:
        cleaned = []
        for o in origins:
            o = o.strip()
            if not o:
                continue
            if not o.startswith(("http://", "https://")):
                raise ValueError(f"Origin must start with http:// or https:// — got: {o}")
            cleaned.append(o)
        return cleaned


class WidgetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    widget_type: Optional[str] = Field(default=None, max_length=50)
    fields_config: Optional[List[FieldDefinition]] = Field(default=None, max_length=20)
    allowed_origins: Optional[List[str]] = Field(default=None, max_length=20)
    webhook_url: Optional[str] = Field(default=None, max_length=2048)
    notify_email: Optional[str] = Field(default=None, max_length=512)
    is_active: Optional[bool] = None


class WidgetResponse(BaseModel):
    id: uuid.UUID
    public_id: str
    name: str
    description: Optional[str]
    widget_type: str
    fields_config: list
    allowed_origins: List[str]
    webhook_url: Optional[str]
    notify_email: Optional[str]
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SnippetResponse(BaseModel):
    snippet: str
    public_id: str
    version: int
