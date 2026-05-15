"""
Routine API
===========
Endpoints:
  POST   /routines/upload          — admin: upload PDF, parse, store
  GET    /routines/active           — get active routine for a department
  GET    /routines/slots            — query slots by day/teacher/room/batch
  GET    /routines/teacher/{initials}/schedule  — full teacher schedule
  GET    /routines/teacher/{initials}/availability  — availability on a date
  POST   /routines/teacher/override  — teacher: add unavailable/busy block
  DELETE /routines/teacher/override/{id}  — teacher: remove override
"""

import logging
from datetime import date
from typing import Optional
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from pydantic import BaseModel

from app.core.security import get_current_user, require_role
from app.core.supabase import supabase_admin
from app.services.routine.parser import parse_routine_pdf, ParsedRoutine
from app.services.routine.availability import (
    get_teacher_schedule,
    check_teacher_availability,
    get_teacher_free_slots,
    get_teacher_day_summary,
    format_availability_for_ai,
)

import tempfile, os

logger = logging.getLogger("yourDIU.api.routines")
router = APIRouter(prefix="/routines", tags=["Routine"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AvailabilityOverrideCreate(BaseModel):
    date:        date
    time_start:  str          # "10:00"
    time_end:    str          # "11:30"
    status:      str          # "unavailable" | "busy"
    reason:      Optional[str] = None
    public_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Admin: Upload routine PDF
# ---------------------------------------------------------------------------

@router.post("/upload", summary="Upload routine PDF (admin only)")
async def upload_routine(
    file:       UploadFile = File(...),
    department: str        = Form(default="CSE"),
    _admin = Depends(require_role("admin")),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Save to temp file for pdfplumber
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parsed: ParsedRoutine = parse_routine_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not parsed.slots:
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract any slots from PDF. Errors: {parsed.parse_errors}",
        )

    # Upload original PDF to Supabase Storage
    storage_path = f"routines/{department}/{file.filename}"
    try:
        supabase_admin.storage.from_("routines").upload(
            storage_path, content, {"content-type": "application/pdf", "upsert": "true"}
        )
        file_url = supabase_admin.storage.from_("routines").get_public_url(storage_path)
    except Exception as exc:
        logger.warning("Storage upload failed (continuing without it): %s", exc)
        file_url = None

    # Insert routine record (trigger deactivates old ones automatically)
    routine_resp = (
        supabase_admin.table("routines")
        .insert({
            "title":          parsed.title,
            "department":     department,
            "version":        parsed.version,
            "semester":       parsed.semester,
            "effective_from": parsed.effective_from or None,
            "file_url":       file_url,
            "is_active":      True,
        })
        .execute()
    )
    routine_id = routine_resp.data[0]["id"]

    # Batch-insert all parsed slots
    slot_rows = [
        {
            "routine_id":       routine_id,
            "day":              s.day,
            "time_start":       s.time_start,
            "time_end":         s.time_end,
            "room":             s.room,
            "course_code":      s.course_code,
            "batch":            s.batch,
            "section":          s.section,
            "teacher_initials": s.teacher_initials,
            "raw_course_text":  s.raw_course_text,
        }
        for s in parsed.slots
    ]

    # Insert in batches of 500
    for i in range(0, len(slot_rows), 500):
        supabase_admin.table("routine_slots").insert(slot_rows[i:i + 500]).execute()

    return {
        "routine_id":   routine_id,
        "title":        parsed.title,
        "slots_parsed": len(parsed.slots),
        "parse_errors": parsed.parse_errors,
        "file_url":     file_url,
    }


# ---------------------------------------------------------------------------
# Get active routine
# ---------------------------------------------------------------------------

@router.get("/active", summary="Get active routine metadata for a department")
async def get_active_routine(department: str = Query(default="CSE")):
    resp = (
        supabase_admin.table("routines")
        .select("*")
        .eq("department", department)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="No active routine found.")
    return resp.data[0]


# ---------------------------------------------------------------------------
# Query routine slots
# ---------------------------------------------------------------------------

@router.get("/slots", summary="Query class slots")
async def get_slots(
    day:              Optional[str] = Query(None, description="e.g. Saturday"),
    teacher_initials: Optional[str] = Query(None),
    room:             Optional[str] = Query(None),
    course_code:      Optional[str] = Query(None),
    batch:            Optional[str] = Query(None),
    section:          Optional[str] = Query(None),
    department:       str           = Query(default="CSE"),
):
    query = (
        supabase_admin.table("routine_slots")
        .select("*, routines!inner(is_active, department, title, semester)")
        .eq("routines.is_active", True)
        .eq("routines.department", department)
    )
    if day:              query = query.eq("day", day)
    if teacher_initials: query = query.ilike("teacher_initials", teacher_initials)
    if room:             query = query.ilike("room", f"%{room}%")
    if course_code:      query = query.ilike("course_code", f"%{course_code}%")
    if batch:            query = query.eq("batch", batch)
    if section:          query = query.eq("section", section)

    resp = query.order("day").order("time_start").execute()
    return {"slots": resp.data or [], "count": len(resp.data or [])}


# ---------------------------------------------------------------------------
# Teacher schedule
# ---------------------------------------------------------------------------

@router.get("/teacher/{initials}/schedule", summary="Get full schedule for a teacher")
async def teacher_schedule(initials: str):
    slots = get_teacher_schedule(initials.upper())
    if not slots:
        raise HTTPException(status_code=404, detail="No schedule found for this teacher.")
    return {"teacher": initials.upper(), "slots": slots, "count": len(slots)}


# ---------------------------------------------------------------------------
# Teacher availability on a date
# ---------------------------------------------------------------------------

@router.get("/teacher/{initials}/availability", summary="Check teacher availability on a date")
async def teacher_availability(
    initials:  str,
    date_str:  str = Query(..., alias="date", description="YYYY-MM-DD"),
):
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Resolve initials → teacher profile
    profile_resp = (
        supabase_admin.table("teacher_info")
        .select("id, initials, room_number, designation")
        .eq("initials", initials.upper())
        .single()
        .execute()
    )
    if not profile_resp.data:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    teacher_id   = profile_resp.data["id"]
    summary      = get_teacher_day_summary(initials.upper(), teacher_id, target_date)
    free_slots   = get_teacher_free_slots(initials.upper(), teacher_id, target_date)

    return {
        **summary,
        "free_slots":   free_slots,
        "room_number":  profile_resp.data.get("room_number"),
        "designation":  profile_resp.data.get("designation"),
        "ai_context":   format_availability_for_ai(summary),
    }


# ---------------------------------------------------------------------------
# Teacher: add availability override
# ---------------------------------------------------------------------------

@router.post("/teacher/override", summary="Add unavailable/busy block (teacher or admin)")
async def add_override(
    body:         AvailabilityOverrideCreate,
    current_user  = Depends(get_current_user),
):
    # Verify the user is a teacher or admin
    profile = (
        supabase_admin.table("profiles")
        .select("role")
        .eq("id", current_user.id)
        .single()
        .execute()
    )
    role = profile.data.get("role", "student") if profile.data else "student"
    if role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Only teachers and admins can add overrides.")

    if body.status not in ("unavailable", "busy"):
        raise HTTPException(status_code=400, detail="status must be 'unavailable' or 'busy'.")

    resp = (
        supabase_admin.table("teacher_availability")
        .upsert({
            "teacher_id":   current_user.id,
            "date":         body.date.isoformat(),
            "time_start":   body.time_start,
            "time_end":     body.time_end,
            "status":       body.status,
            "reason":       body.reason,
            "public_note":  body.public_note,
            "created_by":   role,
        }, on_conflict="teacher_id,date,time_start,time_end")
        .execute()
    )
    return {"override": resp.data[0], "message": "Override saved."}


@router.delete("/teacher/override/{override_id}", summary="Remove an availability override")
async def delete_override(
    override_id:  str,
    current_user  = Depends(get_current_user),
):
    # Only owner or admin can delete
    existing = (
        supabase_admin.table("teacher_availability")
        .select("teacher_id")
        .eq("id", override_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Override not found.")

    if existing.data["teacher_id"] != current_user.id:
        # Check if admin
        profile = (
            supabase_admin.table("profiles")
            .select("role").eq("id", current_user.id).single().execute()
        )
        if profile.data.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not authorized.")

    supabase_admin.table("teacher_availability").delete().eq("id", override_id).execute()
    return {"message": "Override removed."}
