"""Widget management router — authenticated, tenant-isolated CRUD.

Every query filters by `current_user.tenant_id`. A tenant can only see,
create, update, or delete their own widgets. There is no path to access
another tenant's widgets.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.tenant import User
from app.models.widget import Widget
from app.schemas.widget import (
    SnippetResponse,
    WidgetCreate,
    WidgetResponse,
    WidgetUpdate,
)
from app.services.snippet import generate_snippet

router = APIRouter(prefix="/api/v1/widgets", tags=["widgets"])


def _get_owned_widget(
    widget_id: str,
    current_user: User,
    db: Session,
) -> Widget:
    """Fetch a widget by UUID, scoped to the current user's tenant."""
    try:
        wid = __import__("uuid").UUID(widget_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    widget = (
        db.query(Widget)
        .filter(Widget.id == wid, Widget.tenant_id == current_user.tenant_id)
        .first()
    )
    if not widget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    return widget


def _generate_public_id() -> str:
    """16-char URL-safe ID for the public embed endpoint."""
    return secrets.token_urlsafe(12)[:16]


@router.post("", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
def create_widget(
    body: WidgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    widget = Widget(
        tenant_id=current_user.tenant_id,
        public_id=_generate_public_id(),
        name=body.name,
        description=body.description,
        widget_type=body.widget_type,
        fields_config=[f.model_dump() for f in body.fields_config],
        allowed_origins=body.allowed_origins,
        webhook_url=body.webhook_url,
        notify_email=body.notify_email,
    )
    db.add(widget)
    db.commit()
    db.refresh(widget)
    return widget


@router.get("", response_model=list[WidgetResponse])
def list_widgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Widget)
        .filter(Widget.tenant_id == current_user.tenant_id)
        .order_by(Widget.created_at.desc())
        .all()
    )


@router.get("/{widget_id}", response_model=WidgetResponse)
def get_widget(
    widget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_widget(widget_id, current_user, db)


@router.put("/{widget_id}", response_model=WidgetResponse)
def update_widget(
    widget_id: str,
    body: WidgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    widget = _get_owned_widget(widget_id, current_user, db)

    update_data = body.model_dump(exclude_unset=True)
    if "fields_config" in update_data and update_data["fields_config"] is not None:
        update_data["fields_config"] = [f.model_dump() for f in body.fields_config]
    if "allowed_origins" in update_data and update_data["allowed_origins"] is not None:
        update_data["allowed_origins"] = body.allowed_origins

    for key, val in update_data.items():
        setattr(widget, key, val)

    widget.version += 1  # bump cache version on any update
    db.commit()
    db.refresh(widget)
    return widget


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(
    widget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    widget = _get_owned_widget(widget_id, current_user, db)
    db.delete(widget)
    db.commit()


@router.get("/{widget_id}/snippet", response_model=SnippetResponse)
def get_snippet(
    widget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    widget = _get_owned_widget(widget_id, current_user, db)
    snippet = generate_snippet(widget)
    return SnippetResponse(
        snippet=snippet,
        public_id=widget.public_id,
        version=widget.version,
    )
