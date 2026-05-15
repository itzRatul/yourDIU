"""
Notices API
===========
Endpoints:
  GET    /notices              — list notices (paginated, filter by category/dept)
  POST   /notices              — admin creates notice
  GET    /notices/{id}         — get one notice
  PATCH  /notices/{id}         — admin updates notice
  DELETE /notices/{id}         — admin deletes notice
  POST   /notices/{id}/pin     — admin pins/unpins a notice
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator

from app.core.security import get_optional_user, get_current_user, require_role
from app.core.supabase import supabase_admin

logger = logging.getLogger("yourDIU.api.notices")
router = APIRouter(prefix="/notices", tags=["Notices"])

VALID_CATEGORIES = {"academic", "exam", "event", "admission", "general", "department"}


# ── Models ───────────────────────────────────────────────────────────────────

class NoticeCreate(BaseModel):
    title:      str
    content:    str
    category:   str = "general"
    department: Optional[str] = None   # None = all departments
    attachment_url: Optional[str] = None
    is_pinned:  bool = False
    expires_at: Optional[str] = None   # ISO datetime string

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty.")
        return v.strip()

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(VALID_CATEGORIES)}")
        return v


class NoticeUpdate(BaseModel):
    title:          Optional[str] = None
    content:        Optional[str] = None
    category:       Optional[str] = None
    department:     Optional[str] = None
    attachment_url: Optional[str] = None
    expires_at:     Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", summary="List notices")
async def list_notices(
    category:   Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    pinned_only: bool         = Query(False),
    limit:      int           = Query(default=20, le=100),
    offset:     int           = Query(default=0),
    _user=Depends(get_optional_user),
):
    query = (
        supabase_admin.table("notices")
        .select("*, profiles!notices_created_by_fkey(full_name)")
        .eq("is_active", True)
        .order("is_pinned", desc=True)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if category:
        query = query.eq("category", category)
    if department:
        # department-specific OR all-departments notices
        query = query.or_(f"department.eq.{department},department.is.null")
    if pinned_only:
        query = query.eq("is_pinned", True)

    resp = query.execute()
    return {"notices": resp.data or [], "count": len(resp.data or [])}


@router.post("", summary="Create a notice (admin only)")
async def create_notice(
    body:        NoticeCreate,
    current_user=Depends(require_role("admin")),
):
    notice_id = str(uuid.uuid4())
    resp = (
        supabase_admin.table("notices")
        .insert({
            "id":             notice_id,
            "created_by":     current_user.id,
            "title":          body.title,
            "content":        body.content,
            "category":       body.category,
            "department":     body.department,
            "attachment_url": body.attachment_url,
            "is_pinned":      body.is_pinned,
            "expires_at":     body.expires_at,
            "is_active":      True,
        })
        .execute()
    )

    # Push notification to all users
    _push_notice_notification(notice_id, body.title, body.category)

    return {"notice": resp.data[0], "message": "Notice created."}


@router.get("/{notice_id}", summary="Get a single notice")
async def get_notice(
    notice_id: str,
    _user=Depends(get_optional_user),
):
    resp = (
        supabase_admin.table("notices")
        .select("*, profiles!notices_created_by_fkey(full_name)")
        .eq("id", notice_id)
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Notice not found.")
    return resp.data


@router.patch("/{notice_id}", summary="Update a notice (admin only)")
async def update_notice(
    notice_id: str,
    body:      NoticeUpdate,
    _admin=Depends(require_role("admin")),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update.")

    existing = (
        supabase_admin.table("notices")
        .select("id")
        .eq("id", notice_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Notice not found.")

    resp = (
        supabase_admin.table("notices")
        .update(data)
        .eq("id", notice_id)
        .execute()
    )
    return {"notice": resp.data[0], "message": "Notice updated."}


@router.delete("/{notice_id}", summary="Delete (soft) a notice (admin only)")
async def delete_notice(
    notice_id: str,
    _admin=Depends(require_role("admin")),
):
    existing = (
        supabase_admin.table("notices")
        .select("id")
        .eq("id", notice_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Notice not found.")

    # Soft delete
    supabase_admin.table("notices").update({"is_active": False}).eq("id", notice_id).execute()
    return {"message": "Notice removed."}


@router.post("/{notice_id}/pin", summary="Pin or unpin a notice (admin only)")
async def toggle_pin(
    notice_id: str,
    _admin=Depends(require_role("admin")),
):
    existing = (
        supabase_admin.table("notices")
        .select("id, is_pinned")
        .eq("id", notice_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Notice not found.")

    new_pin = not existing.data["is_pinned"]
    supabase_admin.table("notices").update({"is_pinned": new_pin}).eq("id", notice_id).execute()
    return {"is_pinned": new_pin, "message": "Pinned." if new_pin else "Unpinned."}


# ── Internal helper ──────────────────────────────────────────────────────────

def _push_notice_notification(notice_id: str, title: str, category: str):
    """Insert a broadcast notification row for this notice."""
    try:
        supabase_admin.table("notifications").insert({
            "id":        str(uuid.uuid4()),
            "user_id":   None,   # NULL = broadcast to all
            "type":      "notice",
            "title":     f"New Notice: {title}",
            "body":      f"Category: {category}",
            "ref_id":    notice_id,
            "ref_type":  "notice",
        }).execute()
    except Exception as e:
        logger.warning("Failed to push notice notification: %s", e)
