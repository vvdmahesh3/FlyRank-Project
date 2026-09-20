"""Pydantic schemas for the owner dashboard API."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_widgets: int
    total_submissions: int
    submissions_today: int
    submissions_this_week: int
    submissions_by_status: dict[str, int]
    submissions_by_country: dict[str, int]
    top_widgets: List[dict]


class DashboardSubmissionItem(BaseModel):
    id: uuid.UUID
    widget_id: uuid.UUID
    widget_name: str
    data: dict
    submitter_ip: Optional[str]
    geo_country: Optional[str]
    geo_city: Optional[str]
    status: str
    spam_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedSubmissions(BaseModel):
    items: List[DashboardSubmissionItem]
    total: int
    page: int
    page_size: int
    has_next: bool
