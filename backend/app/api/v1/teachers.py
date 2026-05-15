"""
Teacher Info API
================
  GET  /teachers              — list all teachers with info
  GET  /teachers/{id}         — get one teacher's full info
  PUT  /teachers/me           — teacher updates own info (room, office hours, etc.)
  PUT  /teachers/{id}         — admin updates any teacher's info
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import get_current_user, require_role
from app.core.supabase import supabase_admin

logger = logging.getLogger("yourDIU.api.teachers")
router = APIRouter(prefix="/teachers", tags=["Teachers"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class OfficeHourSlot(BaseModel):
    day:   str    # "Sunday"
    start: str    # "10:00"
    end:   str    # "12:00"


class TeacherInfoUpdate(BaseModel):
    employee_id:     Optional[str]              = None
    initials:        Optional[str]              = None   # e.g. "MAK"
    designation:     Optional[str]              = None   # "Associate Professor"
    department:      Optional[str]              = None
    room_number:     Optional[str]              = None   # office room
    office_building: Optional[str]              = None
    office_hours:    Optional[list[OfficeHourSlot]] = None
    phone:           Optional[str]              = None
    personal_website: Optional[str]             = None


# ---------------------------------------------------------------------------
# List teachers
# ---------------------------------------------------------------------------

@router.get("", summary="List all teachers with their info")
async def list_teachers(
    department: Optional[str] = Query(None),
    search:     Optional[str] = Query(None, description="Search by name or initials"),
):
    query = (
        supabase_admin.table("teacher_info")
        .select("*, profiles!inner(full_name, email, avatar_url, role)")
        .eq("profiles.role", "teacher")
    )
    if department:
        query = query.eq("department", department)

    resp = query.execute()
    teachers = resp.data or []

    if search:
        s = search.lower()
        teachers = [
            t for t in teachers
            if s in (t.get("initials") or "").lower()
            or s in (t.get("profiles", {}).get("full_name") or "").lower()
        ]

    return {"teachers": teachers, "count": len(teachers)}


# ---------------------------------------------------------------------------
# Get one teacher
# ---------------------------------------------------------------------------

@router.get("/{teacher_id}", summary="Get teacher profile + info")
async def get_teacher(teacher_id: str):
    resp = (
        supabase_admin.table("teacher_info")
        .select("*, profiles!inner(full_name, email, avatar_url)")
        .eq("id", teacher_id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return resp.data


# ---------------------------------------------------------------------------
# Teacher updates own info
# ---------------------------------------------------------------------------

@router.put("/me", summary="Teacher updates own room/office hours/info")
async def update_my_info(
    body:         TeacherInfoUpdate,
    current_user  = Depends(get_current_user),
):
    profile = (
        supabase_admin.table("profiles")
        .select("role").eq("id", current_user.id).single().execute()
    )
    if not profile.data or profile.data.get("role") not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Only teachers can update their info.")

    data = body.model_dump(exclude_none=True)
    if "office_hours" in data:
        data["office_hours"] = [oh.model_dump() for oh in body.office_hours]

    # Upsert teacher_info row
    data["id"] = current_user.id
    resp = (
        supabase_admin.table("teacher_info")
        .upsert(data, on_conflict="id")
        .execute()
    )
    return {"teacher_info": resp.data[0], "message": "Info updated."}


# ---------------------------------------------------------------------------
# Admin updates any teacher's info
# ---------------------------------------------------------------------------

@router.put("/{teacher_id}", summary="Admin updates teacher info (admin only)")
async def admin_update_teacher(
    teacher_id:   str,
    body:         TeacherInfoUpdate,
    _admin        = Depends(require_role("admin")),
):
    data = body.model_dump(exclude_none=True)
    if "office_hours" in data:
        data["office_hours"] = [oh.model_dump() for oh in body.office_hours]

    data["id"] = teacher_id
    resp = (
        supabase_admin.table("teacher_info")
        .upsert(data, on_conflict="id")
        .execute()
    )
    return {"teacher_info": resp.data[0], "message": "Teacher info updated."}
