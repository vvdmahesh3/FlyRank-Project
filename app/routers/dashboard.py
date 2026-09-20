"""Owner dashboard router — authenticated, tenant-isolated.

Provides aggregate stats and paginated submission listings. All queries
filter by `current_user.tenant_id`.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.submission import Submission
from app.models.tenant import User
from app.models.widget import Widget
from app.schemas.dashboard import (
    DashboardStats,
    DashboardSubmissionItem,
    PaginatedSubmissions,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = current_user.tenant_id

    total_widgets = (
        db.query(func.count(Widget.id))
        .filter(Widget.tenant_id == tenant_id)
        .scalar()
    )

    total_submissions = (
        db.query(func.count(Submission.id))
        .filter(Submission.tenant_id == tenant_id)
        .scalar()
    )

    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_week = now - timedelta(days=7)

    submissions_today = (
        db.query(func.count(Submission.id))
        .filter(Submission.tenant_id == tenant_id, Submission.created_at >= start_today)
        .scalar()
    )

    submissions_this_week = (
        db.query(func.count(Submission.id))
        .filter(Submission.tenant_id == tenant_id, Submission.created_at >= start_week)
        .scalar()
    )

    # Submissions by status
    status_rows = (
        db.query(Submission.status, func.count(Submission.id))
        .filter(Submission.tenant_id == tenant_id)
        .group_by(Submission.status)
        .all()
    )
    by_status = {row[0]: row[1] for row in status_rows}

    # Submissions by country
    country_rows = (
        db.query(Submission.geo_country, func.count(Submission.id))
        .filter(
            Submission.tenant_id == tenant_id,
            Submission.geo_country.isnot(None),
        )
        .group_by(Submission.geo_country)
        .all()
    )
    by_country = {row[0] or "Unknown": row[1] for row in country_rows}

    # Top widgets by submission count
    top_widget_rows = (
        db.query(
            Widget.id,
            Widget.name,
            func.count(Submission.id).label("count"),
        )
        .outerjoin(Submission, Submission.widget_id == Widget.id)
        .filter(Widget.tenant_id == tenant_id)
        .group_by(Widget.id, Widget.name)
        .order_by(func.count(Submission.id).desc())
        .limit(5)
        .all()
    )
    top_widgets = [
        {"id": str(row[0]), "name": row[1], "submissions": row[2]}
        for row in top_widget_rows
    ]

    return DashboardStats(
        total_widgets=total_widgets or 0,
        total_submissions=total_submissions or 0,
        submissions_today=submissions_today or 0,
        submissions_this_week=submissions_this_week or 0,
        submissions_by_status=by_status,
        submissions_by_country=by_country,
        top_widgets=top_widgets,
    )


@router.get("/submissions", response_model=PaginatedSubmissions)
def list_submissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = current_user.tenant_id
    query = (
        db.query(Submission, Widget.name.label("widget_name"))
        .join(Widget, Submission.widget_id == Widget.id)
        .filter(Submission.tenant_id == tenant_id)
        .order_by(Submission.created_at.desc())
    )

    if status_filter:
        query = query.filter(Submission.status == status_filter)

    total = query.count()
    offset = (page - 1) * page_size
    rows = query.offset(offset).limit(page_size).all()

    items = []
    for submission, widget_name in rows:
        item = DashboardSubmissionItem(
            id=submission.id,
            widget_id=submission.widget_id,
            widget_name=widget_name,
            data=submission.data,
            submitter_ip=str(submission.submitter_ip) if submission.submitter_ip else None,
            geo_country=submission.geo_country,
            geo_city=submission.geo_city,
            status=submission.status,
            spam_score=submission.spam_score,
            created_at=submission.created_at,
        )
        items.append(item)

    return PaginatedSubmissions(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total,
    )


@router.get("/widgets/{widget_id}/submissions", response_model=PaginatedSubmissions)
def list_widget_submissions(
    widget_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import uuid as _uuid

    try:
        wid = _uuid.UUID(widget_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    # Ensure widget belongs to this tenant
    widget = (
        db.query(Widget)
        .filter(Widget.id == wid, Widget.tenant_id == current_user.tenant_id)
        .first()
    )
    if not widget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    query = (
        db.query(Submission)
        .filter(Submission.widget_id == wid, Submission.tenant_id == current_user.tenant_id)
        .order_by(Submission.created_at.desc())
    )

    total = query.count()
    offset = (page - 1) * page_size
    submissions = query.offset(offset).limit(page_size).all()

    items = [
        DashboardSubmissionItem(
            id=s.id,
            widget_id=s.widget_id,
            widget_name=widget.name,
            data=s.data,
            submitter_ip=str(s.submitter_ip) if s.submitter_ip else None,
            geo_country=s.geo_country,
            geo_city=s.geo_city,
            status=s.status,
            spam_score=s.spam_score,
            created_at=s.created_at,
        )
        for s in submissions
    ]

    return PaginatedSubmissions(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total,
    )
