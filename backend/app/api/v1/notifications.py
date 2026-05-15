"""
Notifications API
=================
Endpoints:
  GET    /notifications              — list my notifications (unread first)
  PATCH  /notifications/{id}/read   — mark one as read
  POST   /notifications/read-all    — mark all as read
  DELETE /notifications/{id}        — delete one notification
  GET    /notifications/unread-count — quick badge count

Notification types:
  notice          — new notice posted
  community_reply — someone replied to your post/comment
  routine_change  — routine was updated
  teacher_update  — teacher marked unavailable
  system          — general system message

Broadcast (user_id = NULL) notifications are returned to all users.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import get_current_user, require_role
from app.core.supabase import supabase_admin

logger = logging.getLogger("yourDIU.api.notifications")
router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ── Models ───────────────────────────────────────────────────────────────────

class NotificationCreate(BaseModel):
    user_id:  Optional[str] = None   # None = broadcast
    type:     str
    title:    str
    body:     Optional[str] = None
    ref_id:   Optional[str] = None
    ref_type: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", summary="List my notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit:       int  = Query(default=30, le=100),
    offset:      int  = Query(default=0),
    current_user=Depends(get_current_user),
):
    """
    Returns personal notifications + broadcast (user_id IS NULL) notifications.
    Unread first, then by created_at desc.
    """
    query = (
        supabase_admin.table("notifications")
        .select("*")
        .or_(f"user_id.eq.{current_user.id},user_id.is.null")
        .order("is_read")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if unread_only:
        query = query.eq("is_read", False)

    resp = query.execute()
    return {"notifications": resp.data or [], "count": len(resp.data or [])}


@router.get("/unread-count", summary="Get unread notification count (for badge)")
async def unread_count(current_user=Depends(get_current_user)):
    resp = (
        supabase_admin.table("notifications")
        .select("id", count="exact")
        .or_(f"user_id.eq.{current_user.id},user_id.is.null")
        .eq("is_read", False)
        .execute()
    )
    return {"unread_count": resp.count or 0}


@router.patch("/{notification_id}/read", summary="Mark a notification as read")
async def mark_read(
    notification_id: str,
    current_user=Depends(get_current_user),
):
    existing = (
        supabase_admin.table("notifications")
        .select("id, user_id")
        .eq("id", notification_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Notification not found.")

    # Only owner can mark personal notifications; broadcasts anyone can mark
    n_user = existing.data.get("user_id")
    if n_user and n_user != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized.")

    supabase_admin.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
    return {"message": "Marked as read."}


@router.post("/read-all", summary="Mark all my notifications as read")
async def mark_all_read(current_user=Depends(get_current_user)):
    # Mark personal notifications
    supabase_admin.table("notifications").update({"is_read": True}).eq("user_id", current_user.id).eq("is_read", False).execute()
    # Mark broadcast notifications (user_id IS NULL)
    supabase_admin.table("notifications").update({"is_read": True}).is_("user_id", "null").eq("is_read", False).execute()
    return {"message": "All notifications marked as read."}


@router.delete("/{notification_id}", summary="Delete a notification")
async def delete_notification(
    notification_id: str,
    current_user=Depends(get_current_user),
):
    existing = (
        supabase_admin.table("notifications")
        .select("id, user_id")
        .eq("id", notification_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Notification not found.")

    n_user = existing.data.get("user_id")
    if n_user and n_user != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized.")

    supabase_admin.table("notifications").delete().eq("id", notification_id).execute()
    return {"message": "Notification deleted."}


# ── Admin: send notification manually ────────────────────────────────────────

@router.post("/send", summary="Send a notification (admin only)")
async def send_notification(
    body:   NotificationCreate,
    _admin=Depends(require_role("admin")),
):
    """
    Admin can send a targeted or broadcast notification.
    user_id=None → broadcast to all users.
    """
    resp = (
        supabase_admin.table("notifications")
        .insert({
            "id":       str(uuid.uuid4()),
            "user_id":  body.user_id,
            "type":     body.type,
            "title":    body.title,
            "body":     body.body,
            "ref_id":   body.ref_id,
            "ref_type": body.ref_type,
        })
        .execute()
    )
    return {"notification": resp.data[0], "message": "Notification sent."}
